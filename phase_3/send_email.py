"""
Send Phase 3 email drafts to configured alias via SMTP.

Usage:
  python send_email.py --week 2026-W11
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from config import OUTPUT_DIR, ALIAS_EMAIL


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def _load_draft(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid draft JSON: {path}")
    return data


def _send_smtp(subject: str, body: str, recipient: str) -> None:
    smtp_host = _required_env("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = _required_env("SMTP_USER")
    smtp_pass = _required_env("SMTP_PASS")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user).strip()

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=60) as server:
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def send_draft_for_week(week: str, *, output_dir: str = OUTPUT_DIR) -> str:
    out_path = Path(output_dir)
    draft_file = out_path / f"email_draft_{week}.json"
    if not draft_file.exists():
        raise FileNotFoundError(f"Draft file not found: {draft_file}")

    draft = _load_draft(draft_file)
    subject = str(draft.get("subject") or "").strip()
    body = str(draft.get("body") or "").strip()
    recipient = str(draft.get("recipient") or ALIAS_EMAIL or "").strip()
    if not subject or not body:
        raise ValueError("Draft subject/body is empty")
    if not recipient:
        raise ValueError("No recipient found (draft.recipient and ALIAS_EMAIL are empty)")

    _send_smtp(subject, body, recipient)
    return recipient


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Phase 3 email draft to alias via SMTP")
    parser.add_argument("--week", "-w", required=True, help="Week id, e.g. 2026-W11")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="Output directory with email_draft_*.json")
    args = parser.parse_args()

    recipient = send_draft_for_week(args.week, output_dir=args.output)
    print(f"Email sent successfully to {recipient}")


if __name__ == "__main__":
    main()

