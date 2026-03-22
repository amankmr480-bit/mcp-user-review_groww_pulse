"""
Phase 4: PII sanitization helpers (used by Phase 3).

Goal: ensure generated notes and email drafts contain no user-identifying data
(emails, phone numbers, and common id-like tokens).
"""

from __future__ import annotations

import re
from typing import Iterable


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"\b\+?\d[\d\s\-().]{7,}\d\b")

# Looks like a UUID (v1-v5) or generic 32-hex ids.
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HEX32_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")

# Our internal ids/tokens should never appear in note/email content.
_INTERNAL_TOKEN_RE = re.compile(r"\b(?:th_|qt_|ac_|note_|draft_)[A-Za-z0-9_\\-]+\b")


def sanitize_text(text: str) -> str:
    """Redact common PII patterns and internal id-like tokens."""
    t = text or ""
    t = _EMAIL_RE.sub("[redacted-email]", t)
    t = _PHONE_RE.sub("[redacted-phone]", t)
    t = _UUID_RE.sub("[redacted-id]", t)
    t = _HEX32_RE.sub("[redacted-id]", t)
    t = _INTERNAL_TOKEN_RE.sub("[redacted-id]", t)
    return t


def find_pii_findings(text: str) -> list[str]:
    """Return human-readable PII matches (used for validation)."""
    t = text or ""
    findings: list[str] = []
    if _EMAIL_RE.search(t):
        findings.append("email")
    if _PHONE_RE.search(t):
        findings.append("phone")
    if _UUID_RE.search(t) or _HEX32_RE.search(t):
        findings.append("id-like")
    if _INTERNAL_TOKEN_RE.search(t):
        findings.append("internal-token")
    return findings


def word_count(text: str) -> int:
    """Approx word count used for the ≤250 words constraint."""
    return len((text or "").split())


def enforce_word_limit(text: str, *, max_words: int = 250) -> str:
    """Truncate by words to max_words (no ellipsis needed)."""
    words = (text or "").split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def sanitize_and_enforce(
    text: str,
    *,
    max_words: int = 250,
) -> tuple[str, dict[str, bool]]:
    """Sanitize + enforce word limit. Returns sanitized_text and flags."""
    original_wc = word_count(text)
    sanitized = sanitize_text(text)
    sanitized_wc = word_count(sanitized)
    truncated = False
    if sanitized_wc > max_words:
        sanitized = enforce_word_limit(sanitized, max_words=max_words)
        truncated = True
    flags = {"was_truncated": truncated, "original_wc_gt_limit": original_wc > max_words}
    return sanitized, flags


def assert_no_pii(text: str, *, allowed_findings: Iterable[str] = ()) -> None:
    """Raise ValueError if disallowed PII patterns are found."""
    findings = find_pii_findings(text)
    allowed = set(allowed_findings)
    disallowed = [f for f in findings if f not in allowed]
    if disallowed:
        raise ValueError(f"PII validation failed: {', '.join(disallowed)}")

