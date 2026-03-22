"""
Phase 3: Generate weekly one-page notes + email drafts from Phase 2 analysis.

Uses GROQ to assemble:
- ≤250-word note content
- email subject + body (body = note content)

Then Phase 4 sanitization/validation is applied to ensure no PII is present.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import INPUT_DIR, OUTPUT_DIR, GROQ_MODEL, ALIAS_EMAIL, MAX_NOTE_WORDS, GROQ_API_KEY
from groq_client import chat_completion_json

# Ensure repo root is on sys.path so `phase_4` can be imported when running from `phase_3/`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phase_4.sanitize import assert_no_pii, sanitize_and_enforce, sanitize_text, word_count


NOTE_SYSTEM_PROMPT = """You write weekly product notes for app review themes (GROWW).
Rules (must follow):
- Output MUST be valid JSON only (no markdown, no extra text).
- Never include usernames, emails, phone numbers, or any user identifiers.
- Never include internal ids like theme_id, quote_id, action_id, review_id.
- Keep the output concise: note content must be <=250 words.
- Email subject must not contain any PII.
Return strings that contain no PII.
"""


NOTE_USER_TEMPLATE = """week_id: {week_id}

Top themes (ranked):
{themes_block}

Quotes (sanitized):
{quotes_block}

Action ideas (3 bullets):
{actions_block}

Task:
1. Write ONE one-page weekly note (Markdown is OK) that covers:
   - the top themes (briefly)
   - the 3 quotes (verbatim, already sanitized)
   - the 3 action ideas as a short prioritized list
2. Ensure note_content is <= {max_words} words.
3. Create email_subject: "GROWW Weekly Review Note — Week {week_id}"
4. email_body MUST be exactly the note_content.

Output JSON shape:
{{
  "note_content": "...",
  "email_subject": "...",
  "email_body": "..."
}}
"""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _discover_analysis_files(input_dir: Path) -> list[Path]:
    return sorted(input_dir.glob("analysis_*.json"))


def _load_analysis_file(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid analysis file: {path}")
    return data


def _format_themes(analysis: dict[str, Any], *, top_k: int = 3) -> str:
    themes = analysis.get("themes") or []
    if not isinstance(themes, list):
        themes = []
    # Ensure rank ordering.
    def _rank(t: dict[str, Any]) -> int:
        try:
            return int(t.get("rank", 999))
        except Exception:
            return 999

    themes_sorted = sorted((t for t in themes if isinstance(t, dict)), key=_rank)[:top_k]
    lines = []
    for t in themes_sorted:
        label = str(t.get("label") or "").strip()
        desc = str(t.get("description") or "").strip()
        rank = t.get("rank")
        rank_s = f"(rank {rank})" if rank is not None else ""
        if desc:
            lines.append(f"- {label} {rank_s}: {desc}".strip())
        else:
            lines.append(f"- {label} {rank_s}".strip())
    return "\n".join(lines)


def _format_quotes(analysis: dict[str, Any]) -> str:
    themes = analysis.get("themes") or []
    theme_by_id: dict[str, str] = {}
    if isinstance(themes, list):
        for t in themes:
            if isinstance(t, dict) and t.get("theme_id") and t.get("label"):
                theme_by_id[str(t["theme_id"])] = str(t["label"])

    quotes = analysis.get("quotes") or []
    if not isinstance(quotes, list):
        quotes = []

    out_lines = []
    for q in quotes[:3]:
        if not isinstance(q, dict):
            continue
        txt = str(q.get("text") or "").strip()
        tid = str(q.get("theme_id") or "").strip()
        tlabel = theme_by_id.get(tid, "")
        if tlabel:
            out_lines.append(f"- {tlabel}: \"{txt}\"")
        else:
            out_lines.append(f'- "{txt}"')
    return "\n".join(out_lines)


def _format_actions(analysis: dict[str, Any]) -> str:
    actions = analysis.get("actions") or []
    if not isinstance(actions, list):
        actions = []

    # Sort by order if provided.
    def _order(a: dict[str, Any]) -> int:
        try:
            return int(a.get("order", 999))
        except Exception:
            return 999

    actions_sorted = sorted((a for a in actions if isinstance(a, dict)), key=_order)[:3]
    lines = []
    for a in actions_sorted:
        txt = str(a.get("text") or "").strip()
        order = a.get("order")
        if order is not None:
            lines.append(f"{order}. {txt}")
        else:
            lines.append(f"- {txt}")
    return "\n".join(lines)


def _sanitize_and_validate_note_fields(
    *,
    note_content: str,
    email_subject: str,
    email_body: str,
    max_words: int,
) -> tuple[str, str, str]:
    # Sanitize + enforce word limit on note content, then sanitize subject/body.
    note_s, _flags = sanitize_and_enforce(note_content, max_words=max_words)
    subj_s = sanitize_text(email_subject)
    body_s = sanitize_text(email_body)

    # Ensure body equals note content for correctness.
    # (We sanitize both separately, so compare sanitized versions.)
    if body_s != note_s:
        body_s = note_s

    # Final validation for no PII patterns.
    assert_no_pii(note_s)
    assert_no_pii(subj_s)
    assert_no_pii(body_s)

    # Enforce word limit again (sanitization could slightly change split).
    if word_count(note_s) > max_words:
        note_s = " ".join(note_s.split()[:max_words])
        body_s = note_s

    return note_s, subj_s, body_s


def generate_for_week(
    analysis: dict[str, Any],
    *,
    week_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    note_id = _new_id("note")
    draft_id = _new_id("draft")

    if not dry_run and not ALIAS_EMAIL.strip():
        raise ValueError("ALIAS_EMAIL is not set (Phase 3 config). It must come from env/config only.")

    if dry_run:
        note_content = f"Weekly Review ({week_id})\n\nThemes and actions are generated with GROQ in real runs."
        email_subject = f"GROWW Weekly Review Note — Week {week_id}"
        email_body = note_content
    else:
        themes_block = _format_themes(analysis, top_k=3)
        quotes_block = _format_quotes(analysis)
        actions_block = _format_actions(analysis)

        user_prompt = NOTE_USER_TEMPLATE.format(
            week_id=week_id,
            themes_block=themes_block,
            quotes_block=quotes_block,
            actions_block=actions_block,
            max_words=MAX_NOTE_WORDS,
        )

        resp = chat_completion_json(NOTE_SYSTEM_PROMPT, user_prompt, temperature=0.2)
        if not isinstance(resp, dict):
            raise ValueError("GROQ note generation did not return a dict")

        note_content = str(resp.get("note_content") or "").strip()
        email_subject = str(resp.get("email_subject") or "").strip()
        email_body = str(resp.get("email_body") or "").strip()
        if not note_content or not email_subject or not email_body:
            raise ValueError("GROQ note generation missing required fields")

    note_content_s, email_subject_s, email_body_s = _sanitize_and_validate_note_fields(
        note_content=note_content,
        email_subject=email_subject,
        email_body=email_body,
        max_words=MAX_NOTE_WORDS,
    )
    wc = word_count(note_content_s)

    # Pick top themes for metadata references.
    themes = analysis.get("themes") or []
    top_theme_ids: list[str] = []
    if isinstance(themes, list):
        def _rank(t: dict[str, Any]) -> int:
            try:
                return int(t.get("rank", 999))
            except Exception:
                return 999

        themes_sorted = sorted((t for t in themes if isinstance(t, dict)), key=_rank)[:3]
        for t in themes_sorted:
            if t.get("theme_id"):
                top_theme_ids.append(str(t["theme_id"]))

    quote_ids: list[str] = []
    for q in (analysis.get("quotes") or [])[:3]:
        if isinstance(q, dict) and q.get("quote_id"):
            quote_ids.append(str(q["quote_id"]))

    action_ids: list[str] = []
    for a in (analysis.get("actions") or [])[:3]:
        if isinstance(a, dict) and a.get("action_id"):
            action_ids.append(str(a["action_id"]))

    note_obj = {
        "note_id": note_id,
        "week_id": week_id,
        "content": note_content_s,
        "top_theme_ids": top_theme_ids,
        "quote_ids": quote_ids,
        "action_ids": action_ids,
        "word_count": wc,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    email_obj = {
        "draft_id": draft_id,
        "week_id": week_id,
        "note_id": note_id,
        "subject": email_subject_s,
        "body": email_body_s,
        "recipient": ALIAS_EMAIL.strip() if ALIAS_EMAIL.strip() else None,
    }

    return {"note": note_obj, "email": email_obj}


def run(
    input_dir: str = INPUT_DIR,
    output_dir: str = OUTPUT_DIR,
    *,
    week: Optional[str] = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    files = _discover_analysis_files(in_path)
    if week:
        files = [p for p in files if p.stem == f"analysis_{week}" or week in p.name]

    if not files:
        raise FileNotFoundError(f"No analysis_*.json under {in_path}")

    summaries: list[dict[str, Any]] = []
    for fp in files:
        analysis = _load_analysis_file(fp)
        week_id = str(analysis.get("week_id") or fp.stem.replace("analysis_", ""))

        generated = generate_for_week(analysis, week_id=week_id, dry_run=dry_run)
        note_obj = generated["note"]
        email_obj = generated["email"]

        note_file = out_path / f"weekly_note_{week_id}.json"
        email_file = out_path / f"email_draft_{week_id}.json"
        with open(note_file, "w", encoding="utf-8") as f:
            json.dump(note_obj, f, indent=2, ensure_ascii=False)
        with open(email_file, "w", encoding="utf-8") as f:
            json.dump(email_obj, f, indent=2, ensure_ascii=False)

        # Human-friendly markdown (optional but useful).
        md_file = out_path / f"weekly_note_{week_id}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(str(note_obj.get("content") or "").rstrip() + "\n")

        summaries.append(
            {
                "week_id": week_id,
                "note": str(note_file),
                "email_draft": str(email_file),
                "summary_md": str(md_file),
                "word_count": note_obj.get("word_count"),
            }
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3: Generate weekly note + email draft from Phase 2 analysis.")
    parser.add_argument("--input", "-i", default=INPUT_DIR, help="Directory with analysis_*.json from Phase 2")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="Output directory for weekly notes")
    parser.add_argument("--week", "-w", default=None, help="Only process one week id e.g. 2026-W11")
    parser.add_argument("--dry-run", action="store_true", help="Skip GROQ; generate placeholder notes")
    args = parser.parse_args()

    if not GROQ_API_KEY.strip() and not args.dry_run:
        raise ValueError("GROQ_API_KEY is not set. Put it in phase_3/.env or export env var.")

    summaries = run(input_dir=args.input, output_dir=args.output, week=args.week, dry_run=args.dry_run)
    print("Phase 3 complete.")
    for s in summaries:
        print(f"  {s['week_id']}: word_count={s.get('word_count')} note={s['note']} email={s['email_draft']}")


if __name__ == "__main__":
    main()

