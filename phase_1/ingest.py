"""
Phase 1: Ingest Play Store reviews from public export (CSV).
- Reads CSV from configured path (Play Console export or compatible).
- Drops PII columns; keeps only review_id, text, rating, date, week_id.
- Excludes reviews with fewer than 4 words or only emojis.
- Caps total output at MAX_TOTAL_REVIEWS (newest first).
- Writes weekly batches to output directory.
"""
from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import (
    COLUMN_MAPPING,
    DATE_FORMATS,
    INPUT_PATH,
    MAX_TOTAL_REVIEWS,
    MIN_WORDS_IN_REVIEW,
    OUTPUT_DIR,
    PII_COLUMNS,
)


def _find_column(row: dict, keys: list[str]) -> Optional[str]:
    """Return first matching column name from row (case-insensitive)."""
    row_lower = {k.strip().lower(): k for k in row.keys()}
    for key in keys:
        if key.lower() in row_lower:
            return row_lower[key.lower()]
    return None


def _parse_date(value: str) -> Optional[datetime]:
    """Parse date string using common formats."""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _week_id(dt: datetime) -> str:
    """Return ISO week id e.g. 2025-W10."""
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _is_too_few_words(text: str) -> bool:
    """True if text has fewer than MIN_WORDS_IN_REVIEW words (after stripping)."""
    if not text or not isinstance(text, str):
        return True
    words = text.strip().split()
    return len(words) < MIN_WORDS_IN_REVIEW


def _is_emoji_only(text: str) -> bool:
    """True if text contains no letters and no digits (only emojis/symbols/space)."""
    if not text or not isinstance(text, str):
        return True
    # Remove whitespace; require at least one letter or digit for "not emoji-only"
    cleaned = re.sub(r"\s+", "", text)
    return not any(c.isalnum() for c in cleaned)


def _should_skip_review(text: str) -> bool:
    """Skip if fewer than 4 words or content is only emojis."""
    return _is_too_few_words(text) or _is_emoji_only(text)


def _review_id(text: str, date_str: str, rating: Any, index: int) -> str:
    """Stable opaque id for the review (no PII)."""
    raw = f"{text}|{date_str}|{rating}|{index}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _normalize_rating(value: Any) -> Optional[int]:
    """Coerce rating to int 1-5."""
    if value is None or value == "":
        return None
    try:
        r = int(float(value))
        if 1 <= r <= 5:
            return r
    except (ValueError, TypeError):
        pass
    return None


def load_csv(path: str) -> list[dict]:
    """Load CSV and return list of row dicts. Tries UTF-8 and common fallbacks."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path} with encodings: {encodings}")


def map_columns(headers: list[str]) -> dict[str, str]:
    """Map our schema keys to actual CSV column names."""
    valid = [h for h in headers if h is not None and str(h).strip()]
    row_lower = {h.strip().lower(): h.strip() for h in valid}
    result = {}
    for schema_key, candidates in COLUMN_MAPPING.items():
        for c in candidates:
            if c.lower() in row_lower:
                result[schema_key] = row_lower[c.lower()]
                break
    return result


def ingest(input_path: str = INPUT_PATH, output_dir: str = OUTPUT_DIR) -> dict[str, Any]:
    """
    Ingest CSV, filter one-word reviews, strip PII, partition by week.
    Returns stats and writes one JSON file per week under output_dir.
    """
    import json

    rows = load_csv(input_path)
    if not rows:
        return {"total_rows": 0, "skipped_few_words": 0, "skipped_emoji_only": 0, "written": 0, "weeks": [], "message": "No rows in CSV"}

    col_map = map_columns(list(rows[0].keys()))
    if "date" not in col_map or "text" not in col_map:
        raise ValueError(
            "CSV must have date and text columns. "
            f"Found columns: {list(rows[0].keys())}. "
            "See config.COLUMN_MAPPING for supported names."
        )
    date_col = col_map["date"]
    text_col = col_map["text"]
    rating_col = col_map.get("rating")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    skipped_few_words = 0
    skipped_emoji_only = 0
    skipped_no_date = 0
    skipped_no_rating = 0
    all_records: list[dict] = []

    for i, row in enumerate(rows):
        raw_text = (row.get(text_col) or "").strip()
        if _is_too_few_words(raw_text):
            skipped_few_words += 1
            continue
        if _is_emoji_only(raw_text):
            skipped_emoji_only += 1
            continue
        raw_date = row.get(date_col) or ""
        dt = _parse_date(raw_date)
        if not dt:
            skipped_no_date += 1
            continue
        rating = _normalize_rating(row.get(rating_col) if rating_col else None)
        if rating is None:
            rating = 0
        week_id = _week_id(dt)
        rid = _review_id(raw_text, raw_date, rating, i)
        record = {
            "review_id": rid,
            "text": raw_text,
            "rating": rating,
            "date": dt.strftime("%Y-%m-%d"),
            "week_id": week_id,
        }
        all_records.append(record)

    # Cap total rows (newest first)
    if MAX_TOTAL_REVIEWS > 0 and len(all_records) > MAX_TOTAL_REVIEWS:
        all_records.sort(key=lambda r: r["date"], reverse=True)
        all_records = all_records[:MAX_TOTAL_REVIEWS]
        # Re-sort by date ascending for consistent weekly grouping
        all_records.sort(key=lambda r: r["date"])

    weekly: dict[str, list[dict]] = {}
    for record in all_records:
        weekly.setdefault(record["week_id"], []).append(record)

    # Write one file per week
    written = 0
    for week_id, reviews in sorted(weekly.items()):
        out_path = Path(output_dir) / f"reviews_{week_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(reviews, f, indent=2, ensure_ascii=False)
        written += len(reviews)

    stats = {
        "total_rows": len(rows),
        "skipped_few_words": skipped_few_words,
        "skipped_emoji_only": skipped_emoji_only,
        "skipped_no_date": skipped_no_date,
        "skipped_no_rating": skipped_no_rating,
        "written": written,
        "weeks": sorted(weekly.keys()),
        "output_dir": output_dir,
        "max_total_reviews": MAX_TOTAL_REVIEWS,
    }
    # Write ingestion stats
    with open(Path(output_dir) / "_ingest_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    return stats


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Phase 1: Ingest Play Store reviews from public CSV export.")
    parser.add_argument("--input", "-i", default=INPUT_PATH, help="Path to input CSV")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="Output directory for weekly JSON files")
    args = parser.parse_args()
    stats = ingest(input_path=args.input, output_dir=args.output)
    print("Ingest complete.")
    print(f"  Total rows:           {stats['total_rows']}")
    print(f"  Skipped (<4 words):   {stats.get('skipped_few_words', 0)}")
    print(f"  Skipped (emoji only): {stats.get('skipped_emoji_only', 0)}")
    print(f"  Skipped (no date):    {stats.get('skipped_no_date', 0)}")
    print(f"  Written (cap {stats.get('max_total_reviews', 0)}): {stats['written']} reviews in {len(stats['weeks'])} weeks")
    print(f"  Output dir:           {stats['output_dir']}")
    print(f"  Weeks:                {stats['weeks']}")


if __name__ == "__main__":
    main()
