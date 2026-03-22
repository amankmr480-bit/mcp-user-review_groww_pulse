# Phase 3: Notes + Email Drafts

This phase takes Phase 2 analysis (`analysis_{week_id}.json`) and generates:

- A one-page weekly note (`weekly_note_{week_id}.json` + `weekly_note_{week_id}.md`)
- An email draft (`email_draft_{week_id}.json`)

The note content is constrained to **<= 250 words** and is validated/sanitized by **Phase 4** so that no PII appears.

## Setup

1. Configure Phase 3 secrets:
   - Edit `phase_3/.env` and set:
     - `GROQ_API_KEY`
     - `ALIAS_EMAIL` (the only recipient allowed; e.g. your own email or alias)
2. Install deps:

```powershell
cd "e:\Gen AI bootcamp\MCP user review\phase_3"
pip install -r requirements.txt
```

## Run

Generate all weeks found in Phase 2:

```powershell
cd "e:\Gen AI bootcamp\MCP user review\phase_3"
python generate_notes.py
```

Generate a single week:

```powershell
python generate_notes.py --week 2026-W11
```

Dry run (no GROQ calls; creates placeholder note/email for pipeline checks):

```powershell
python generate_notes.py --dry-run --week 2026-W11
```

## Output

By default, outputs to `phase_3/output/`:

- `weekly_note_{week_id}.json`
- `weekly_note_{week_id}.md`
- `email_draft_{week_id}.json`

## Send Draft To Alias

Phase 3 includes `send_email.py` for SMTP delivery of the generated draft:

```powershell
cd "e:\Gen AI bootcamp\MCP user review\phase_3"
python send_email.py --week 2026-W11
```

Required SMTP env vars (can be set in shell or `.env`):

- `SMTP_HOST` (e.g. `smtp.gmail.com`)
- `SMTP_PORT` (default `465`)
- `SMTP_USER`
- `SMTP_PASS`
- optional `SMTP_FROM` (defaults to `SMTP_USER`)

