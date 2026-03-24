# Phase-Wise Architecture: GROWW App Play Store Review AI Workflow

**Purpose:** Import 8 weeks of GROWW app Play Store reviews, analyze with GROQQ LLM, and produce weekly one-page notes with themes, quotes, action ideas, and email drafts—**UI and orchestration on Streamlit (Phase 5)**. Production deployment targets **Streamlit** (e.g. Streamlit Community Cloud). An optional **FastAPI** in `phase_5` serves HTTP clients only; there is **no separate Next.js / Vercel app** in this repository.

**Constraints:** Public exports only • Max 5 themes • Notes ≤250 words • No PII (usernames, emails, IDs) in any artifact • Phase 1: min 4 words per review, exclude emoji-only, max 800 total rows.

---

## High-Level Design

### System Context

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                     EXTERNAL BOUNDARY                            │
                    │  ┌──────────────────┐                                            │
                    │  │ Play Store       │  (Public CSV / API export only)             │
                    │  │ Review Source   │──────────────────────┐                      │
                    │  └──────────────────┘                      │                      │
                    └───────────────────────────────────────────│──────────────────────┘
                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              GROWW REVIEW AI WORKFLOW                                                 │
│                                                                                                       │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                   │
│   │  Ingestion   │────▶│   Storage    │────▶│  GROQQ LLM   │────▶│ Note + Email │                   │
│   │  (Phase 1)   │     │  (reviews,   │     │  (Phase 2)   │     │  (Phase 3)   │                   │
│   │  PII strip   │     │   by week)   │     │  themes,     │     │  ≤250 words  │                   │
│   └──────────────┘     └──────────────┘     │  quotes,     │     │  draft only  │                   │
│                                             │  actions     │     └───────┬──────┘                   │
│                                             └──────────────┘             │                          │
│                                                                          │                          │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────────┐  │
│   │  UI + ORCHESTRATION (Streamlit, Phase 5)                                                      │  │
│   │  • Week-by-date (YYYY-MM-DD)  • Run pipeline  • View weekly note + email draft               │  │
│   │  • Trigger import  • Run analysis  • Generate note  • Send email to self/alias               │  │
│   │  Reads/writes artifacts under phase_1 / phase_2 / phase_3 on the host (same repo layout).     │  │
│   └──────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                       │
│   Optional: FastAPI (`phase_5/api.py`) for HTTP clients / automation (not required for Streamlit UI). │  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| **Source** | Play Store (public) | Supply 8 weeks of reviews via CSV/API export; no scraping. |
| **Ingestion** | ETL / pipeline | Fetch, date-filter, PII-strip; persist by `week_id`. |
| **Storage** | DB / object store | Hold `Review`, `WeeklyNote`, `EmailDraft`; no PII. |
| **Analysis** | GROQQ LLM | Themes (3–5), 3 quotes (sanitized), 3 action ideas per week. |
| **Generation** | Note assembler | One-page note (≤250 words) + email subject/body. |
| **UI + orchestration** | Streamlit (`phase_5/streamlit_app.py`) | Full layout: week date, pipeline controls, weekly note, email draft, send to alias (in-process pipeline). |
| **Optional HTTP API** | FastAPI (`phase_5/api.py`) | REST surface for external tools or custom frontends; not required to operate the Streamlit app. |

### Data Flow (Logical)

1. **Import:** Play Store export → Ingestion → `Review` records (no PII) keyed by week.
2. **Analyze:** Per week, reviews → GROQQ → `Theme`, `Quote`, `ActionIdea` (stored or in-memory).
3. **Generate:** Themes + quotes + actions → Note template → `WeeklyNote` + `EmailDraft`.
4. **Consume:** Streamlit reads note/draft JSON from `phase_3/output/` (optional FastAPI exposes the same data over HTTP).
5. **Send (optional):** User action “Send to alias” → `send_email.py` uses configured SMTP + recipient from env/secrets.

---

## Data Model

### Entity Relationship (Logical)

- **Review** — raw input per review (post PII strip).
- **Theme** — derived per week; 3–5 per week.
- **Quote** — sanitized user quote; 3 per week; linked to a theme.
- **ActionIdea** — actionable item; 3 per week.
- **WeeklyNote** — one-page note per week; references top 3 themes, 3 quotes, 3 actions.
- **EmailDraft** — subject + body per week; body = note content; recipient = config only.

Relationships: **Review** grouped by **week** → **Theme** / **Quote** / **ActionIdea** produced per week → **WeeklyNote** and **EmailDraft** generated per week.

---

### Entity Definitions

#### Review (ingested; no PII)

| Field | Type | Description |
|-------|------|-------------|
| `review_id` | string (opaque) | Unique id for the review (e.g. hash or source id); not user id. |
| `text` | string | Review body (PII redacted if present in source). |
| `rating` | number (1–5) | Star rating. |
| `date` | date/datetime | When the review was posted. |
| `week_id` | string | Week partition, e.g. `"2025-W01"` or `YYYY-MM-DD` start. |

**Constraints:** No `user_id`, `username`, or `email`. Used only for aggregation and LLM input.

---

#### Theme (analysis output)

| Field | Type | Description |
|-------|------|-------------|
| `theme_id` | string | Unique id for the theme instance. |
| `week_id` | string | Week this theme belongs to. |
| `label` | string | Short name (e.g. "Login issues", "UI clarity"). |
| `description` | string (optional) | Optional one-line description. |
| `rank` | number (optional) | 1–5; used to pick “top 3” for the note. |

**Constraints:** Max 5 themes per `week_id`.

---

#### Quote (analysis output; sanitized)

| Field | Type | Description |
|-------|------|-------------|
| `quote_id` | string | Unique id. |
| `week_id` | string | Week this quote belongs to. |
| `theme_id` | string | Link to Theme. |
| `text` | string | Sanitized quote (no usernames, emails, IDs). |

**Constraints:** 3 quotes per week (e.g. one per top theme or 3 across themes).

---

#### ActionIdea (analysis output)

| Field | Type | Description |
|-------|------|-------------|
| `action_id` | string | Unique id. |
| `week_id` | string | Week this action belongs to. |
| `text` | string | Short actionable bullet (e.g. "Improve login error messages"). |
| `order` | number (optional) | 1–3 for display order. |

**Constraints:** Exactly 3 per week.

---

#### WeeklyNote (generated artifact)

| Field | Type | Description |
|-------|------|-------------|
| `note_id` | string | Unique id. |
| `week_id` | string | Week (e.g. `"2025-W01"`). |
| `week_label` | string (optional) | Human label, e.g. "Week of 2025-01-06". |
| `content` | string | One-page note (Markdown or plain text); ≤250 words. |
| `top_theme_ids` | list[string] (optional) | References to top 3 Theme ids. |
| `quote_ids` | list[string] (optional) | References to 3 Quote ids. |
| `action_ids` | list[string] (optional) | References to 3 ActionIdea ids. |
| `word_count` | number | Must be ≤250. |
| `created_at` | datetime | When the note was generated. |

**Constraints:** No PII in `content`.

---

#### EmailDraft (generated artifact)

| Field | Type | Description |
|-------|------|-------------|
| `draft_id` | string | Unique id. |
| `week_id` | string | Same week as WeeklyNote. |
| `note_id` | string | Reference to WeeklyNote (body = note content). |
| `subject` | string | e.g. "GROWW Weekly Review Note — Week YYYY-MM-DD". |
| `body` | string | Same as note content; no PII. |
| `recipient` | string | From config only (self/alias); never from review data. |
| `sent_at` | datetime (optional) | When email was sent, if applicable. |

**Constraints:** Recipient is a single configured address; no user emails from reviews.

---

#### Config / Run Metadata (optional)

| Field | Type | Description |
|-------|------|-------------|
| `source_type` | string | e.g. "play_store_csv", "public_api". |
| `weeks_requested` | number | e.g. 8. |
| `alias_email` | string | Self/alias for “send to self”; from env/config. |
| `last_ingest_at` | datetime | Last successful import. |

Stored in env or a small config table; no PII from reviews.

---

### Data Model Diagram (Logical)

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Review    │       │   Theme     │       │   Quote     │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ review_id   │       │ theme_id    │       │ quote_id    │
│ text        │       │ week_id     │◀──────│ week_id     │
│ rating      │       │ label       │       │ theme_id    │
│ date        │       │ description │       │ text        │
│ week_id     │       │ rank        │       └─────────────┘
└──────┬──────┘       └──────┬──────┘              │
       │                     │                     │
       │  grouped by week_id │                     │
       └────────────────────┼─────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐       ┌─────────────┐
                   │  ActionIdea     │       │ WeeklyNote  │
                   ├─────────────────┤       ├─────────────┤
                   │ action_id       │       │ note_id     │
                   │ week_id         │       │ week_id     │
                   │ text            │       │ content     │
                   │ order           │       │ top_theme_ids
                   └────────┬────────┘       │ quote_ids   │
                            │                │ action_ids  │
                            └────────────────│ word_count  │
                                             └──────┬──────┘
                                                    │
                                                    ▼
                                             ┌─────────────┐
                                             │ EmailDraft  │
                                             ├─────────────┤
                                             │ draft_id    │
                                             │ week_id     │
                                             │ note_id     │
                                             │ subject     │
                                             │ body        │
                                             │ recipient   │
                                             │ sent_at     │
                                             └─────────────┘
```

---

## Phase 1: Data Ingestion & Source Strategy

### 1.1 Review Data Source
- **Primary:** Use **public** Play Store review export mechanisms only:
  - **Google Play Console CSV export** (if you have app owner/developer access) — export is a download, not scraping.
  - **Third-party public APIs/datasets** that provide Play Store reviews without login (e.g. documented, ToS-compliant review datasets or public archives).
  - **RSS/Atom feeds** or **public review aggregator APIs** that expose reviews without authentication.
- **Explicit exclusions:** No headless browsers, no scraping behind login walls, no use of credentials to bypass access controls.

### 1.2 Data Pipeline
- **Input:** 8 weeks of reviews (date-filtered) in a structured format (CSV/JSON).
- **Storage:** Temporary or persistent store (e.g. cloud storage bucket, DB table) keyed by `week_id` and `review_timestamp`.
- **Schema (logical):** `review_id`, `text`, `rating`, `date`, `week_number` — **no** `user_id`, `username`, or `email`.
- **PII stripping at ingest:** Before any analysis, strip or hash any fields that could contain PII; only `text`, `rating`, `date`, `week_number` flow downstream.
- **Ingest filters:**
  - Exclude reviews with **fewer than 4 words** (short/no-content reviews).
  - Exclude reviews that contain **only emojis** (no letters or digits).
- **Cap:** Limit total rows to **800** (newest first by date); then partition by week.

### 1.3 Output of Phase 1
- Weekly batches of reviews (e.g. up to 8 files or partitions), **max 800 reviews total**, each containing only non-PII fields, ready for Phase 2.

---

## Phase 2: Analysis Pipeline (GROQQ LLM)

### 2.1 LLM Integration
- **Model:** GROQQ as the LLM for all analysis and generation steps.
- **Interface:** REST/API client to GROQQ (configurable endpoint and API key via env/secrets).
- **Rate limits & retries:** Throttling and backoff for API calls; optional batching of reviews per request.
- **Implementation (`phase_2/`):** Reviews are batched **per map request** (default **25** reviews per call, env `PHASE2_REVIEW_BATCH_SIZE`), then **one reduce call per week** merges batch summaries into final themes, quotes, and actions. Approx. `ceil(N/25) + 1` GROQ calls per week for `N` reviews.

### 2.2 Theming (3–5 Themes)
- **Input:** Aggregated review text per week (or per 8-week window, depending on product choice).
- **Prompt design:**
  - Instruct GROQQ to derive **3–5 themes** from the review corpus.
  - Themes must be **labels or short phrases** (e.g. "Login issues", "UI clarity", "Performance").
  - No extraction of usernames, emails, or user identifiers.
- **Output:** Structured list of 3–5 theme names + optional short descriptions per theme.
- **Validation:** Post-process to enforce max 5 themes; drop or merge if more are returned.

### 2.3 Quote Selection
- **Input:** Same review corpus + chosen themes.
- **Task:** For each theme (or for “top 3” themes in the note), select **3 user quotes** that best represent the theme.
- **PII rule:** Strip or redact any segment that looks like username, email, phone, or ID before storing; store only sanitized quote text.
- **Output:** 3 quotes (e.g. one per top theme, or 3 across themes) with theme tag, no attribution to user.

### 2.4 Action Ideas
- **Input:** Themes + optional summary of sentiment/feedback.
- **Task:** GROQQ generates **3 action ideas** (product/ops/support) based on the themes.
- **Output:** 3 short, actionable bullet points (e.g. "Improve login error messages", "Add in-app FAQ for common errors").

### 2.5 Output of Phase 2
- Per week (or per run): **themes (3–5)**, **3 sanitized quotes**, **3 action ideas**, plus any minimal metadata (e.g. week range, theme list) for the note.

---

## Phase 3: One-Page Note & Email Draft

### 3.1 Note Assembly
- **Template:** One-page note containing:
  1. **Top 3 themes** (from Phase 2; if more than 3 themes, pick top 3 by relevance/volume).
  2. **3 user quotes** (sanitized, no PII).
  3. **3 action ideas.**
- **Word limit:** Enforce ≤250 words (prompt + post-process truncation or summarization).
- **Format:** Plain text or light Markdown; scannable (headings, bullets).

### 3.2 Email Draft
- **Content:** Body = one-page note; subject line = e.g. "GROWW Weekly Review Note — Week YYYY-MM-DD".
- **Recipient:** Self or alias only (configurable email address; no user emails from reviews).
- **No PII:** Draft must not contain any usernames, emails, or IDs from the source data.

### 3.3 Email Sending (Optional)
- **Mechanism:** Use a transactional email provider (e.g. SendGrid, Resend, SES) or SMTP with credentials in env.
- **Flow:** "Send to self/alias" = single recipient from config; no dynamic recipient from review data.

### 3.4 Output of Phase 3
- **Artifacts:** Weekly one-page note (≤250 words), email draft (subject + body), and optional “sent” status.
- **Storage:** Save note and draft in a form that the frontend can display (e.g. JSON/file per week).

---

## Phase 4: Privacy & Compliance

### 4.1 PII Handling
- **Definition:** Usernames, emails, user IDs, phone numbers, and any identifier that can link to a person.
- **Rules:**
  - Never store or display PII in themes, quotes, action ideas, or email drafts.
  - Sanitize quotes in Phase 2 (pattern-based or LLM-assisted redaction).
  - Logs and errors must not log raw review text that might contain PII (or log only redacted snippets).

### 4.2 Data Retention
- Retain only non-PII fields; define retention period for weekly batches and generated notes (e.g. 90 days then purge or archive).

---

## Phase 5: UI + orchestration (Streamlit) — primary frontend

### 5.1 Responsibilities
- **Single app:** The Streamlit app (`streamlit_app.py`) provides the product UI: title and intro, **Pipeline Controls** card (calendar week via any date `YYYY-MM-DD`, optional “generated week” picker, Phase 2 batch size, optional Phase 1 ingest, buttons: Run Pipeline, Refresh Weeks, Reload Note & Draft, Send To Alias), then **two columns** for **Weekly Note** and **Email Draft** (word count, body, subject/recipient).
- **Orchestration:** Runs the pipeline in-process: `run_pipeline` → Phase 2 analyze + Phase 3 note (and optional Phase 1 ingest); uses `pipeline.py` helpers and repo-relative paths in `config.py` (`phase_1`, `phase_2`, `phase_3`).
- **Styling:** Blue gradient page background and bordered white panels (within Streamlit constraints).
- **Optional REST:** `api.py` (FastAPI) for HTTP integrations (e.g. automation, custom clients); not started when you only run Streamlit.

### 5.2 Deployment
- **Platform:** Streamlit Community Cloud (GitHub repo; main file path e.g. `phase_5/streamlit_app.py`; root `requirements.txt` includes `phase_5` dependencies) or any container/VM running Streamlit.
- **Security:** Secrets (GROQ, SMTP) via Streamlit Cloud **Secrets** or env; no PII in artifacts; HTTPS for hosted app.

---

## End-to-End Flow (Summary)

| Phase | Deliverable |
|-------|-------------|
| 1 | 8 weeks of reviews in non-PII form, partitioned by week |
| 2 | Themes (3–5), 3 sanitized quotes, 3 action ideas per week (GROQQ) |
| 3 | One-page note (≤250 words) + email draft; optional send to self/alias |
| 4 | PII rules applied end-to-end; no PII in any artifact |
| 5 | Streamlit: full UI + ingest, analyze, generate, (optional) send |

---

## Technology Summary (No Implementation)

- **Data:** Public Play Store review export (CSV/API); storage (file/DB) with PII stripped.
- **LLM:** GROQQ for theming, quote selection, action ideas, and note/email copy.
- **Primary UI + orchestration:** Streamlit (`phase_5/streamlit_app.py`).
- **Optional:** FastAPI (`phase_5/api.py`) for REST clients or custom frontends.
- **Email:** SMTP (e.g. Gmail app password); send to self/alias only; no PII in content.

This architecture satisfies: public-only review sources, max 5 themes, ≤250-word scannable notes, no PII in artifacts, and **deployment on Streamlit** for the operator UI.
