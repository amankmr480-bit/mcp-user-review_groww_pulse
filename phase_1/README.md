# Phase 1: Play Store Review Ingestion

Ingests **Groww** app reviews from a **public** Play Store source (scraper or CSV). No login-based access.

**App:** [Groww – Stock, Mutual Fund, Gold](https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en-US) (`com.nextbillion.groww`).

## 1. Export 8 weeks of reviews (optional)

To fetch 8 weeks of reviews (15 Jan 2026 – 15 Mar 2026) from the public Play Store page and write them to the input folder:

```bash
pip install -r requirements.txt
python export_playstore.py
```

This uses the [google-play-scraper](https://github.com/JoMingyu/google-play-scraper) library (public API, no login). The export applies the **same rules as ingest**: drops reviews with fewer than 4 words or only emojis, and caps at 800 rows (newest first). Output is written to `input/reviews.csv` with columns **Review Date**, **Review Text**, **Star Rating** only (no usernames or other PII).

Options:

- `--start`, `--end`: date range (YYYY-MM-DD). Default: 2026-01-15 to 2026-03-15.
- `--output`: path for the CSV (default: `input/reviews.csv`).
- `--lang`, `--country`: e.g. `--lang en --country in` for India.

## 2. Ingest CSV

- **Input:** One CSV file (from `export_playstore.py` above, or from [Google Play Console](https://play.google.com/console) → Your app → Reviews → Export).
- **Filters:** Drops reviews with **fewer than 4 words** or **only emojis** (no letters/digits). Total output is **capped at 800 reviews** (newest first).
- **PII:** Only these fields are kept: `review_id`, `text`, `rating`, `date`, `week_id`. Reviewer name, email, and any user identifiers are never stored.
- **Output:** One JSON file per week under `output/` (e.g. `reviews_2025-W01.json`), plus `_ingest_stats.json` (max 800 reviews across all weeks).

## Expected CSV format

The CSV must have columns for **date** and **review text**. Rating is optional. Supported header names (case-insensitive):

| Our field | Example CSV headers |
|-----------|----------------------|
| date | `Review Date`, `Date`, `review_date`, `Timestamp` |
| text | `Review Text`, `Review`, `Content`, `review_text` |
| rating | `Star Rating`, `Rating`, `rating`, `Score` |

Any other columns (e.g. Reviewer name) are ignored and not written (PII).

Example minimal CSV (use quotes around fields that contain commas, e.g. dates like `Mar 10, 2025`):

```csv
Review Date,Review Text,Star Rating
"Mar 10, 2025","Great app for investing and tracking portfolio.",5
"Mar 9, 2025",Good,4
"Mar 8, 2025","Slow login and confusing UI needs improvement.",2
```

Rows 2 and 3: first is kept (≥4 words); "Good" has fewer than 4 words so that row is **not** exported; third is kept.

## Folder layout (as used by this phase)

When run from the `phase_1` directory:

| Folder   | Purpose |
|----------|---------|
| `input/` | **Input:** Place Play Store export here. Export script writes `input/reviews.csv` by default. |
| `output/`| **Output:** Ingest writes weekly `reviews_YYYY-WNN.json` and `_ingest_stats.json` here (max 800 reviews total). |

Paths are relative to `phase_1/`; config uses `phase_1/input/reviews.csv` and `phase_1/output` when env vars are not set.

## Setup

1. **Export (recommended):** run `python export_playstore.py` to fetch 8 weeks of Groww reviews into `input/reviews.csv`.  
   Or place your own CSV in `phase_1/input/reviews.csv`.
2. Optional: set env vars
   - `PHASE1_INPUT_CSV` – path to CSV (default: `phase_1/input/reviews.csv`)
   - `PHASE1_OUTPUT_DIR` – output directory (default: `phase_1/output`)

## Run

From the `phase_1` directory:

```bash
python ingest.py
```

With custom paths:

```bash
python ingest.py --input /path/to/reviews.csv --output /path/to/output
```

## Output

- `output/reviews_YYYY-WNN.json` – list of review objects per week (only `review_id`, `text`, `rating`, `date`, `week_id`). Max 800 reviews total across all weeks.
- `output/_ingest_stats.json` – counts (total rows, skipped &lt;4 words, skipped emoji-only, written, weeks, max_total_reviews).

No usernames, emails, or user IDs appear in any output file.
