"""
Export Groww app reviews from Google Play Store (public page) for 8 weeks.
Uses google-play-scraper: public API, no login. Writes CSV to input folder (no PII).
Applies same rules as ingest: ≥4 words, not emoji-only, max 800 rows (config).
Date range: 15 Jan 2026 to 15 Mar 2026 (configurable in config.py).
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from config import (
    BASE_DIR,
    EXPORT_END_DATE,
    EXPORT_START_DATE,
    GROWW_APP_ID,
    MAX_TOTAL_REVIEWS,
    MIN_WORDS_IN_REVIEW,
)

try:
    from google_play_scraper import Sort, reviews
except ImportError:
    raise ImportError("Install: pip install google-play-scraper") from None


def _parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD to datetime at start of day."""
    return datetime.strptime(s.strip()[:10], "%Y-%m-%d").replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _is_too_few_words(text: str) -> bool:
    """True if text has fewer than MIN_WORDS_IN_REVIEW words (same rule as ingest)."""
    if not text or not isinstance(text, str):
        return True
    return len(text.strip().split()) < MIN_WORDS_IN_REVIEW


def _is_emoji_only(text: str) -> bool:
    """True if text has no letters/digits (same rule as ingest)."""
    if not text or not isinstance(text, str):
        return True
    cleaned = re.sub(r"\s+", "", text)
    return not any(c.isalnum() for c in cleaned)


def _review_datetime(r: dict) -> datetime | None:
    """Get review date from scraper result (at can be datetime or timestamp)."""
    at = r.get("at")
    if at is None:
        return None
    if isinstance(at, datetime):
        return at.replace(tzinfo=None)
    try:
        return datetime.fromtimestamp(at).replace(tzinfo=None)
    except (TypeError, OSError):
        return None


def fetch_reviews_in_range(
    app_id: str = GROWW_APP_ID,
    start_date: str = EXPORT_START_DATE,
    end_date: str = EXPORT_END_DATE,
    lang: str = "en",
    country: str = "us",
    max_reviews: int = 5000,
) -> list[dict]:
    """
    Fetch reviews from Play Store (newest first), stop when we pass start_date.
    Returns list of dicts with keys: date_str, text, rating. No PII.
    """
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    collected: list[dict] = []
    continuation_token = None
    total_fetched = 0

    while total_fetched < max_reviews:
        try:
            result, continuation_token = reviews(
                app_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=200,
                continuation_token=continuation_token,
            )
        except Exception as e:
            print(f"  Warning: fetch failed ({e}). Using {len(collected)} reviews so far.")
            break

        if not result:
            break

        for r in result:
            dt = _review_datetime(r)
            if dt is None:
                continue
            if dt < start_dt:
                # Past our window; stop pagination
                return collected
            if dt > end_dt:
                continue
            text = (r.get("content") or "").strip()
            score = r.get("score")
            if score is not None and not isinstance(score, int):
                try:
                    score = int(score)
                except (TypeError, ValueError):
                    score = 0
            if score is None or not (1 <= score <= 5):
                score = 0
            collected.append({
                "date_str": dt.strftime("%b %d, %Y"),
                "date_iso": dt.strftime("%Y-%m-%d"),
                "text": text,
                "rating": score,
            })

        total_fetched += len(result)
        if continuation_token is None:
            break

    return collected


def write_csv(rows: list[dict], path: str | Path) -> None:
    """Write CSV with Review Date, Review Text, Star Rating. No PII."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["Review Date", "Review Text", "Star Rating"])
        for r in rows:
            w.writerow([r["date_str"], r["text"], r["rating"]])


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Export Groww Play Store reviews (8 weeks) to input CSV.")
    p.add_argument("--app", default=GROWW_APP_ID, help="Play Store app id")
    p.add_argument("--start", default=EXPORT_START_DATE, help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=EXPORT_END_DATE, help="End date YYYY-MM-DD")
    p.add_argument("--output", "-o", default=str(BASE_DIR / "input" / "reviews.csv"), help="Output CSV path")
    p.add_argument("--lang", default="en", help="Language code")
    p.add_argument("--country", default="us", help="Country code")
    args = p.parse_args()

    print(f"Fetching reviews for {args.app} ({args.start} to {args.end})...")
    rows = fetch_reviews_in_range(
        app_id=args.app,
        start_date=args.start,
        end_date=args.end,
        lang=args.lang,
        country=args.country,
    )
    print(f"  Fetched {len(rows)} reviews in range.")
    # Apply same rules as ingest: ≥4 words, not emoji-only, cap at MAX_TOTAL_REVIEWS
    filtered = []
    skipped_few_words = skipped_emoji = 0
    for r in rows:
        text = (r.get("text") or "").strip()
        if _is_too_few_words(text):
            skipped_few_words += 1
            continue
        if _is_emoji_only(text):
            skipped_emoji += 1
            continue
        filtered.append(r)
    if MAX_TOTAL_REVIEWS > 0 and len(filtered) > MAX_TOTAL_REVIEWS:
        filtered.sort(key=lambda x: x["date_iso"], reverse=True)
        filtered = filtered[:MAX_TOTAL_REVIEWS]
        filtered.sort(key=lambda x: x["date_iso"])
    print(f"  After filter (>={MIN_WORDS_IN_REVIEW} words, no emoji-only): {len(filtered)} (skipped <4 words: {skipped_few_words}, emoji-only: {skipped_emoji})")
    if MAX_TOTAL_REVIEWS > 0:
        print(f"  Capped at {MAX_TOTAL_REVIEWS} rows.")
    write_csv(filtered, args.output)
    print(f"  Wrote {args.output} ({len(filtered)} rows)")
    print("Done. Run ingest.py to process the CSV.")


if __name__ == "__main__":
    main()
