# Phase 6: Frontend (Vercel / Next.js)

This is a Vercel-ready Next.js UI that connects to the Phase 5 backend API.

Features:
- pick the target week by **calendar date** (`YYYY-MM-DD`); the UI shows the resolved ISO week (e.g. `2026-W11`) and Monday start date
- optional dropdown of **generated** weeks (syncs the date field to that week’s Monday)
- view weekly note and email draft
- run pipeline (uses `week_start_date` in the API body)
- send draft to alias
- blue gradient page background

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

Open: `http://localhost:3000`

## Deploy on Vercel

- Import `phase_6` as a project root in Vercel
- Add env var `NEXT_PUBLIC_BACKEND_API_URL` to your deployed Phase 5 API URL

