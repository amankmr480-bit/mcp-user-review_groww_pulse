# Phase 5: Backend (Streamlit + API)

Phase 5 provides:

- **Streamlit control panel** to orchestrate Phase 1 -> 2 -> 3 and send email drafts
- **FastAPI endpoints** for the Phase 6 frontend

## Install

```powershell
cd "e:\Gen AI bootcamp\MCP user review\phase_5"
pip install -r requirements.txt
```

## Run Streamlit Backend Console

```powershell
streamlit run streamlit_app.py
```

## Run API Server

```powershell
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

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

CORS is enabled for `http://localhost:3000` and `http://127.0.0.1:3000` (Phase 6 dev server).

