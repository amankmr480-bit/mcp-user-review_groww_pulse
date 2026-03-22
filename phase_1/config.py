"""
Phase 1 configuration for Play Store review ingestion.
Uses public export only (CSV from Play Console or compatible export).
"""
import os
from pathlib import Path

# Paths (override via env)
BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = os.environ.get("PHASE1_INPUT_CSV", str(BASE_DIR / "input" / "reviews.csv"))
OUTPUT_DIR = os.environ.get("PHASE1_OUTPUT_DIR", str(BASE_DIR / "output"))

# Expected CSV column names (Play Console export and common variants)
# We only keep: date, text, rating. All other columns (e.g. reviewer name) are dropped (PII).
COLUMN_MAPPING = {
    "date": [
        "Review Date",
        "Review date",
        "Date",
        "review_date",
        "date",
        "Timestamp",
    ],
    "text": [
        "Review Text",
        "Review text",
        "Review",
        "Content",
        "review_text",
        "text",
        "Review Content",
    ],
    "rating": [
        "Star Rating",
        "Star rating",
        "Rating",
        "rating",
        "Score",
        "Stars",
    ],
}

# Columns to never include (PII)
PII_COLUMNS = [
    "Reviewer",
    "Reviewer name",
    "User",
    "Username",
    "Email",
    "User name",
    "Author",
    "reviewer",
    "username",
    "email",
    "user_id",
    "UserId",
]

# Date formats commonly used in Play Console exports
DATE_FORMATS = [
    "%b %d, %Y",   # Mar 10, 2025
    "%Y-%m-%d",    # 2025-03-10
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
]

# Filter: minimum word count for review text (reviews with fewer words are excluded)
MIN_WORDS_IN_REVIEW = 4

# Exclude reviews that contain only emojis (no letters/digits).

# Cap total number of reviews written (newest first by date). 0 = no cap.
MAX_TOTAL_REVIEWS = 800

# Groww app on Play Store (for export_playstore.py)
# https://play.google.com/store/apps/details?id=com.nextbillion.groww
GROWW_APP_ID = "com.nextbillion.groww"

# Default 8-week export range: 15 Jan 2026 (start) to 15 Mar 2026 (end)
EXPORT_START_DATE = "2026-01-15"
EXPORT_END_DATE = "2026-03-15"
