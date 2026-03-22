# Phase 2: GROQ analysis

Reads weekly `reviews_*.json` from Phase 1, calls **GROQ** (OpenAI-compatible chat completions), and writes `analysis_{week_id}.json` with:

- **3–5 themes** (`theme_id`, `label`, `description`, `rank`)
- **3 quotes** (sanitized text, `theme_id`)
- **3 action ideas** (`order`)

## Batching (§2.1)

To cut API usage, reviews are processed in **map → reduce**:

1. **Map:** Each request includes up to **`REVIEW_BATCH_SIZE` reviews** (default **25**). The model returns batch-level themes, snippets, and pain points as JSON.
2. **Reduce:** **One** request per week merges all batch summaries into final themes, quotes, and actions.

So for a week with \(N\) reviews, GROQ calls ≈ **`ceil(N / REVIEW_BATCH_SIZE) + 1`** (plus retries only on errors).

Override batch size:

```bash
set PHASE2_REVIEW_BATCH_SIZE=15
```

## Setup

**Option A — `.env` in this folder (recommended)**

1. Copy `.env.example` to `.env` and set your key:

   ```bash
   copy .env.example .env
   ```

2. Edit `.env` and set `GROQ_API_KEY=...` (get a key from [Groq Console](https://console.groq.com/keys)).

3. Install deps so `.env` is loaded:

   ```bash
   pip install -r requirements.txt
   ```

**Option B — environment variable only**

```bash
set GROQ_API_KEY=your_key_here
```

Optional:

- `PHASE2_INPUT_DIR` — folder with `reviews_*.json` (default: `../phase_1/output`)
- `PHASE2_OUTPUT_DIR` — where `analysis_*.json` is written (default: `./output`)
- `GROQ_MODEL` — default `llama-3.1-8b-instant` (override if your key has access to a different model)
- `GROQ_API_URL` — default Groq OpenAI-compatible endpoint
- `GROQ_DEBUG` — set to `1` to print the first ~500 chars of the 4xx/5xx response body
- `GROQ_USE_RESPONSE_FORMAT` — set to `0` if your account/model rejects JSON-mode params

## Run

From this directory:

```powershell
# Optional: confirm the key loads (does not print the key)
python -c "import config; print('OK' if (config.GROQ_API_KEY or '').strip() else 'Set GROQ_API_KEY in .env')"

pip install -r requirements.txt
.\run_phase2.ps1
.\run_phase2.ps1 --week 2026-W11
```

Or without the helper script:

```powershell
python analyze.py
python analyze.py --week 2026-W11
python analyze.py --dry-run
```

`--dry-run` writes placeholder analysis **without** calling GROQ (for pipeline checks).

## Output files

For each week, Phase 2 writes:

- `analysis_{week_id}.json` (structured themes/quotes/actions)
- `analysis_summary_{week_id}.md` (quick human-friendly view)

### If you see `GROQ_API_KEY is not set`

1. **File location:** `phase_2\.env` (same folder as `analyze.py`), not the repo root.
2. **Format:** one line, no spaces around `=`:
   `GROQ_API_KEY=gsk_your_actual_key`
3. **Save the file** after editing; run again from `phase_2`.
4. **Dependencies:** `pip install -r requirements.txt` (optional; a built-in `.env` parser still loads the key if `python-dotenv` is missing).
5. **PowerShell env:** you can instead run `$env:GROQ_API_KEY='gsk_...'` in the same terminal, then `python analyze.py`.

### If you see `HTTP Error 403: Forbidden`

1. Set `GROQ_DEBUG=1` to reveal the response body snippet:

   ```powershell
   set GROQ_DEBUG=1
   python analyze.py --week 2026-W11
   ```

2. If the snippet mentions model access, switch models you can access, e.g.:

   ```powershell
   set GROQ_MODEL=llama-3.1-8b-instant
   python analyze.py --week 2026-W11
   ```

3. If the snippet mentions JSON-mode / `response_format`, disable it:

   ```powershell
   set GROQ_USE_RESPONSE_FORMAT=0
   python analyze.py --week 2026-W11
   ```
