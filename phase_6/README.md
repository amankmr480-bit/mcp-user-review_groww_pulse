# Phase 6: Optional reference frontend (Next.js / Vercel)

**Phase 6 is not required** for the bootcamp product path. The **primary UI** is **Streamlit** in **`phase_5/streamlit_app.py`** (see `ARCHITECTURE.md`).

Keep this folder if you want to experiment with **Next.js + Vercel** and a **separately hosted FastAPI** backend (`uvicorn api:app` from `phase_5`).

## Features (mirror of Streamlit UI)

- Week by **calendar date** (`YYYY-MM-DD`) with resolved ISO week + Monday
- Optional dropdown of **generated** weeks
- Weekly note and email draft
- Run pipeline / send draft (via **HTTP API**, not Streamlit)

## Setup

```powershell
cd "e:\Gen AI bootcamp\MCP user review\phase_6"
copy .env.local.example .env.local
```

Set in `.env.local`:

```env
NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000
```

## Run

```powershell
npm install
npm run dev
```

Open: `http://localhost:3000` (with FastAPI running on port 8000).

## Deploy on Vercel (optional)

- Import **`phase_6`** as the Vercel project **root**
- Set `NEXT_PUBLIC_BACKEND_API_URL` to your **deployed FastAPI** base URL (Streamlit URLs are **not** a substitute for this API)
