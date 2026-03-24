# Phase 5: Primary UI (Streamlit) + optional API (FastAPI)

Phase 5 is the **default product surface**: **Streamlit** implements the full operator UI (same layout as the former Phase 6 Next app — week date, pipeline controls, note + draft columns, blue gradient styling). The pipeline runs **in-process**; you do **not** need Vercel or Phase 6 for this path.

**Optional:** **FastAPI** (`api.py`) exposes REST routes if you want HTTP clients (e.g. automation) or the **optional** Next.js app in `phase_6/`.

## Install

```powershell
cd "e:\Gen AI bootcamp\MCP user review\phase_5"
pip install -r requirements.txt
```

## Run Streamlit (primary UI)

From `phase_5` (so imports resolve):

```powershell
python -m streamlit run streamlit_app.py
```

Or from repo root:

```powershell
cd "e:\Gen AI bootcamp\MCP user review"
python -m streamlit run phase_5/streamlit_app.py
```

## Deploy on Streamlit Community Cloud (GitHub)

- Repository: your GitHub repo (monorepo root).
- **Main file path:** `phase_5/streamlit_app.py`
- Dependencies: root **`requirements.txt`** includes `-r phase_5/requirements.txt`.
- **Secrets:** set `GROQ_API_KEY`, SMTP variables, etc. (same names as Phase 2/3 `.env` expectations).

## Run API server (optional)

```powershell
cd "e:\Gen AI bootcamp\MCP user review\phase_5"
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints (optional FastAPI)

- `GET /health`
- `GET /weeks`
- `GET /week/from-date?date=YYYY-MM-DD` — returns `week_id`, `week_beginning` (ISO Monday), `date`
- `GET /week/from-id?week_id=2026-W11` — same shape, for syncing UI from a generated week id
- `GET /weeks/{week}/note`
- `GET /weeks/{week}/email-draft`
- `POST /pipeline/run` body — prefer **`week_start_date`** (any day in the target week); optional legacy **`week`**:

```json
{
  "week_start_date": "2026-03-17",
  "run_ingest": false,
  "batch_size": 15
}
```

Response includes `resolved_week_id` (e.g. `2026-W12`) and `steps`.

- `POST /weeks/{week}/send`

CORS is enabled for `http://localhost:3000` and `http://127.0.0.1:3000` (optional Phase 6 dev server).
