"""
Phase 2: Analyze weekly review JSON (Phase 1 output) with GROQ.

Uses batched "map" calls: each request includes up to REVIEW_BATCH_SIZE reviews,
then one "reduce" call per week to produce themes (3–5), 3 quotes, 3 actions.
"""
from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import INPUT_DIR, OUTPUT_DIR, REVIEW_BATCH_SIZE
from groq_client import chat_completion_json

# --- Prompts ---

MAP_SYSTEM = """You analyze Play Store-style app reviews for a fintech/investing app (GROWW).
You receive a BATCH of reviews only (not the full week). Extract patterns visible in this batch.
Rules:
- Do NOT invent reviewer names, emails, phone numbers, or user IDs.
- Output MUST be a single JSON object only (no markdown).
- "representative_snippets" must be short phrases from or tightly paraphrasing the reviews, with no PII."""

MAP_USER_TEMPLATE = """Return JSON with keys:
- "bullet_themes": array of 3-6 short theme labels (strings) seen in THIS batch
- "representative_snippets": array of up to 3 strings, each <= 30 words, no PII
- "pain_points": array of up to 3 short strings summarizing problems mentioned

Reviews in this batch (id | stars | text):
{batch_text}
"""

REDUCE_SYSTEM = """You synthesize weekly app review analysis for product teams.
Output MUST be one JSON object only. No usernames, emails, phones, or IDs in any string.
Themes: 3-5 items. Quotes: exactly 3 sanitized snippets. Actions: exactly 3 actionable bullets for product/support."""

REDUCE_USER_TEMPLATE = """week_id: {week_id}

Below are per-batch summaries from the same ISO week (already aggregated from many reviews).
Merge into ONE JSON object with this shape:
{{
  "themes": [ {{"label": "...", "description": "one short line", "rank": 1}} ],
  "quotes": [ {{"theme_label": "must match one theme label", "text": "..."}} ],
  "actions": [ {{"text": "...", "order": 1}} ]
}}

Constraints:
- themes: between 3 and 5 objects; rank 1 = most important this week
- quotes: exactly 3 objects; each text must be a clean user-voice snippet without PII
- actions: exactly 3 objects; order 1..3

Batch summaries (JSON):
{batch_summaries_json}
"""


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _format_review_block(reviews: list[dict[str, Any]]) -> str:
    lines = []
    for r in reviews:
        rid = r.get("review_id", "?")
        rating = r.get("rating", "")
        text = (r.get("text") or "").replace("\n", " ").strip()
        if len(text) > 1200:
            text = text[:1197] + "..."
        lines.append(f"{rid} | {rating} | {text}")
    return "\n".join(lines)


_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
_PHONE_RE = re.compile(r"\b\+?\d[\d\s\-().]{7,}\d\b")


def _sanitize_pii(text: str) -> str:
    t = _EMAIL_RE.sub("[redacted]", text)
    t = _PHONE_RE.sub("[redacted]", t)
    return t


def _normalize_map_response(raw: dict[str, Any]) -> dict[str, Any]:
    themes = raw.get("bullet_themes") or raw.get("themes") or []
    snippets = raw.get("representative_snippets") or raw.get("snippets") or []
    pains = raw.get("pain_points") or raw.get("issues") or []
    if not isinstance(themes, list):
        themes = []
    if not isinstance(snippets, list):
        snippets = []
    if not isinstance(pains, list):
        pains = []
    # Truncate aggressively to keep the weekly reduce prompt small enough.
    return {
        "bullet_themes": [str(t).strip() for t in themes if str(t).strip()][:6],
        "representative_snippets": [_sanitize_pii(str(s).strip()) for s in snippets if str(s).strip()][:3],
        "pain_points": [_sanitize_pii(str(p).strip()) for p in pains if str(p).strip()][:3],
    }


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _clamp_themes(themes: list[dict[str, Any]], week_id: str) -> list[dict[str, Any]]:
    out = []
    for i, t in enumerate(themes[:5]):
        label = str(t.get("label", "")).strip() or f"Theme {i + 1}"
        desc = str(t.get("description", "")).strip()
        rank = t.get("rank")
        try:
            rank_n = int(rank)
        except (TypeError, ValueError):
            rank_n = i + 1
        rank_n = max(1, min(5, rank_n))
        out.append(
            {
                "theme_id": _new_id("th"),
                "week_id": week_id,
                "label": _sanitize_pii(label)[:200],
                "description": _sanitize_pii(desc)[:500] if desc else None,
                "rank": rank_n,
            }
        )
    return out


def _theme_label_to_id(themes: list[dict[str, Any]]) -> dict[str, str]:
    m: dict[str, str] = {}
    for t in themes:
        m[t["label"].lower()] = t["theme_id"]
    return m


def _normalize_final(
    raw: dict[str, Any],
    week_id: str,
) -> dict[str, Any]:
    themes_in = raw.get("themes") or []
    if not isinstance(themes_in, list):
        themes_in = []
    themes = _clamp_themes(
        [
            {
                "label": x.get("label"),
                "description": x.get("description"),
                "rank": x.get("rank"),
            }
            for x in themes_in
            if isinstance(x, dict)
        ],
        week_id,
    )
    themes.sort(key=lambda t: t.get("rank", 99))
    while len(themes) < 3:
        themes.append(
            {
                "theme_id": _new_id("th"),
                "week_id": week_id,
                "label": "General feedback",
                "description": "Mixed or minor themes from this batch.",
                "rank": len(themes) + 1,
            }
        )
    themes = themes[:5]
    label_map = _theme_label_to_id(themes)

    quotes_in = raw.get("quotes") or []
    if not isinstance(quotes_in, list):
        quotes_in = []
    quotes: list[dict[str, Any]] = []
    for x in quotes_in:
        if not isinstance(x, dict):
            continue
        tl = str(x.get("theme_label", "")).strip()
        tid = label_map.get(tl.lower())
        if not tid and themes:
            tid = themes[0]["theme_id"]
        txt = _sanitize_pii(str(x.get("text", "")).strip())
        if txt:
            fallback_theme = themes[0]["theme_id"] if themes else _new_id("th")
            quotes.append(
                {
                    "quote_id": _new_id("qt"),
                    "week_id": week_id,
                    "theme_id": tid or fallback_theme,
                    "text": txt[:800],
                }
            )
    while len(quotes) < 3:
        quotes.append(
            {
                "quote_id": _new_id("qt"),
                "week_id": week_id,
                "theme_id": themes[0]["theme_id"],
                "text": "[No additional distinct quote extracted this week]",
            }
        )
    quotes = quotes[:3]

    actions_in = raw.get("actions") or []
    if not isinstance(actions_in, list):
        actions_in = []
    actions: list[dict[str, Any]] = []
    for x in actions_in:
        if not isinstance(x, dict):
            continue
        txt = _sanitize_pii(str(x.get("text", "")).strip())
        if txt:
            try:
                order = int(x.get("order", len(actions) + 1))
            except (TypeError, ValueError):
                order = len(actions) + 1
            actions.append(
                {
                    "action_id": _new_id("ac"),
                    "week_id": week_id,
                    "text": txt[:500],
                    "order": max(1, min(3, order)),
                }
            )
    actions.sort(key=lambda a: a["order"])
    while len(actions) < 3:
        actions.append(
            {
                "action_id": _new_id("ac"),
                "week_id": week_id,
                "text": "Review weekly feedback trends and prioritize fixes.",
                "order": len(actions) + 1,
            }
        )
    actions = actions[:3]
    for i, a in enumerate(actions, start=1):
        a["order"] = i

    return {
        "week_id": week_id,
        "themes": themes[:5],
        "quotes": quotes,
        "actions": actions,
        "meta": {
            "review_batch_size": REVIEW_BATCH_SIZE,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _dry_run_result(week_id: str, review_count: int, batch_count: int) -> dict[str, Any]:
    return {
        "week_id": week_id,
        "themes": [
            {
                "theme_id": "th_dryrun001",
                "week_id": week_id,
                "label": "Dry run — API key not used",
                "description": "Placeholder theme for pipeline test.",
                "rank": 1,
            },
            {
                "theme_id": "th_dryrun002",
                "week_id": week_id,
                "label": "UI and performance",
                "description": "Example theme slot.",
                "rank": 2,
            },
            {
                "theme_id": "th_dryrun003",
                "week_id": week_id,
                "label": "Support experience",
                "description": "Example theme slot.",
                "rank": 3,
            },
        ],
        "quotes": [
            {
                "quote_id": "qt_dryrun01",
                "week_id": week_id,
                "theme_id": "th_dryrun001",
                "text": "Example quote one (dry run).",
            },
            {
                "quote_id": "qt_dryrun02",
                "week_id": week_id,
                "theme_id": "th_dryrun002",
                "text": "Example quote two (dry run).",
            },
            {
                "quote_id": "qt_dryrun03",
                "week_id": week_id,
                "theme_id": "th_dryrun003",
                "text": "Example quote three (dry run).",
            },
        ],
        "actions": [
            {
                "action_id": "ac_dryrun01",
                "week_id": week_id,
                "text": "Validate GROQ credentials and re-run without --dry-run.",
                "order": 1,
            },
            {
                "action_id": "ac_dryrun02",
                "week_id": week_id,
                "text": "Tune prompts using real weekly output.",
                "order": 2,
            },
            {
                "action_id": "ac_dryrun03",
                "week_id": week_id,
                "text": "Wire Phase 3 note generation from this JSON.",
                "order": 3,
            },
        ],
        "meta": {
            "review_batch_size": REVIEW_BATCH_SIZE,
            "dry_run": True,
            "review_count": review_count,
            "map_api_calls": batch_count,
            "reduce_api_calls": 0,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def analyze_week(
    reviews: list[dict[str, Any]],
    week_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not reviews:
        raise ValueError(f"No reviews for week {week_id}")

    batches = _chunked(reviews, REVIEW_BATCH_SIZE)
    if dry_run:
        return _dry_run_result(week_id, len(reviews), len(batches))

    map_summaries: list[dict[str, Any]] = []
    for batch in batches:
        user = MAP_USER_TEMPLATE.format(batch_text=_format_review_block(batch))
        raw = chat_completion_json(MAP_SYSTEM, user)
        map_summaries.append(_normalize_map_response(raw))

    reduce_user = REDUCE_USER_TEMPLATE.format(
        week_id=week_id,
        batch_summaries_json=json.dumps(map_summaries, ensure_ascii=False),
    )
    final_raw = chat_completion_json(REDUCE_SYSTEM, reduce_user, temperature=0.15)
    result = _normalize_final(final_raw, week_id)
    result["meta"]["map_api_calls"] = len(batches)
    result["meta"]["reduce_api_calls"] = 1
    result["meta"]["review_count"] = len(reviews)
    return result


def load_week_file(path: Path) -> tuple[str, list[dict[str, Any]]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError(f"Invalid or empty week file: {path}")
    week_id = str(data[0].get("week_id") or path.stem.replace("reviews_", ""))
    return week_id, data


def discover_week_files(input_dir: Path) -> list[Path]:
    return sorted(input_dir.glob("reviews_*.json"))


def run(
    input_dir: str = INPUT_DIR,
    output_dir: str = OUTPUT_DIR,
    week: Optional[str] = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    files = discover_week_files(in_path)
    if week:
        files = [p for p in files if p.stem == f"reviews_{week}" or week in p.name]
    if not files:
        raise FileNotFoundError(f"No reviews_*.json under {in_path}")

    summaries: list[dict[str, Any]] = []
    for fp in files:
        if fp.name.startswith("_"):
            continue
        wid, revs = load_week_file(fp)
        analysis = analyze_week(revs, wid, dry_run=dry_run)
        out_file = out_path / f"analysis_{wid}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        # Human-friendly consolidated summary for quick inspection.
        # (No additional PII is introduced; it is derived from the sanitized analysis output.)
        summary_file = out_path / f"analysis_summary_{wid}.md"
        theme_by_id = {t.get("theme_id"): t for t in analysis.get("themes", []) if isinstance(t, dict)}
        quote_theme_label = lambda q: (theme_by_id.get(q.get("theme_id")) or {}).get("label")
        top_themes = analysis.get("themes", [])[:3]

        lines: list[str] = []
        lines.append(f"# Weekly Review Analysis ({wid})")
        lines.append("")
        lines.append("## Top Themes")
        for i, t in enumerate(top_themes, start=1):
            if not isinstance(t, dict):
                continue
            label = t.get("label") or f"Theme {i}"
            desc = t.get("description")
            rank = t.get("rank")
            suffix = f" (rank {rank})" if rank is not None else ""
            lines.append(f"{i}. {label}{suffix}")
            if desc:
                lines.append(f"   - {desc}")
        lines.append("")
        lines.append("## Quotes (sanitized)")
        for q in analysis.get("quotes", [])[:3]:
            if not isinstance(q, dict):
                continue
            txt = q.get("text") or ""
            tl = quote_theme_label(q)
            if tl:
                lines.append(f"- \"{txt}\" (theme: {tl})")
            else:
                lines.append(f"- \"{txt}\"")
        lines.append("")
        lines.append("## Action Ideas")
        for a in analysis.get("actions", [])[:3]:
            if not isinstance(a, dict):
                continue
            order = a.get("order")
            prefix = f"{order}. " if order is not None else "- "
            if prefix.endswith(". "):
                lines.append(f"{prefix}{a.get('text') or ''}")
            else:
                lines.append(f"- {a.get('text') or ''}")

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")

        summaries.append(
            {
                "week_id": wid,
                "output": str(out_file),
                "summary_output": str(summary_file),
                "reviews": len(revs),
                "map_calls": analysis["meta"].get("map_api_calls"),
                "reduce_calls": analysis["meta"].get("reduce_api_calls"),
            }
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2: GROQ analysis with batched reviews per request.")
    parser.add_argument("--input", "-i", default=INPUT_DIR, help="Directory with reviews_*.json from Phase 1")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="Directory for analysis_*.json")
    parser.add_argument("--week", "-w", default=None, help="Only process one week id e.g. 2026-W11")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip GROQ; write placeholder analysis (for pipeline tests).",
    )
    args = parser.parse_args()

    print(f"Review batch size (reviews per map API call): {REVIEW_BATCH_SIZE}")
    if args.dry_run:
        print("Dry run: no GROQ calls.")

    summaries = run(
        input_dir=args.input,
        output_dir=args.output,
        week=args.week,
        dry_run=args.dry_run,
    )
    print("Phase 2 complete.")
    for s in summaries:
        extra = ""
        if s.get("map_calls") is not None:
            extra = f" map_calls={s['map_calls']} reduce_calls={s.get('reduce_calls')}"
        print(f"  {s['week_id']}: {s['reviews']} reviews -> {s['output']}{extra}")
        if s.get("summary_output"):
            print(f"    summary: {s['summary_output']}")


if __name__ == "__main__":
    main()
