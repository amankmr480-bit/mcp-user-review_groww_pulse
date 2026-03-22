# Phase 4: Privacy & Compliance

Phase 4 provides small utilities used by Phase 3 to ensure generated artifacts contain no PII.

## What is validated

Phase 3 calls:

- `phase_4.sanitize.sanitize_and_enforce(...)` to redact:
  - email addresses
  - phone numbers
  - uuid / hex-id like strings
  - internal token patterns (e.g. `th_...`, `qt_...`)
- `phase_4.sanitize.assert_no_pii(...)` to confirm no disallowed patterns remain.

## How to validate Phase 3 outputs (optional)

You can run custom checks by adding a small script, but the default Phase 3 generation already enforces:

- Weekly note `content` word count <= `PHASE3_MAX_NOTE_WORDS` (default 250)
- No PII in `note_content`, `email_subject`, and `email_body`

