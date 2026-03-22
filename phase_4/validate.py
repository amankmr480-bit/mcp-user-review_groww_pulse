"""
Phase 4: privacy & compliance validation.

This module provides:
- `validate_no_pii_outputs(...)` for Phase 3 artifacts
- helper checks for word limits and missing fields
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sanitize import assert_no_pii, word_count


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


def validate_no_pii_outputs(artifact: dict[str, Any], *, paths: list[str]) -> ValidationResult:
    """
    Validate each `artifact[path]` string contains no disallowed PII.
    `paths` is a list of dot-separated keys like ["content"] or ["email.body"].
    """
    errors: list[str] = []
    for p in paths:
        cur: Any = artifact
        for k in p.split("."):
            if not isinstance(cur, dict) or k not in cur:
                cur = None
                break
            cur = cur[k]
        if not isinstance(cur, str):
            continue
        try:
            assert_no_pii(cur)
        except ValueError as e:
            errors.append(f"{p}: {e}")
    return ValidationResult(ok=not errors, errors=errors)


def validate_word_limit(note_content: str, *, max_words: int = 250) -> ValidationResult:
    wc = word_count(note_content)
    if wc <= max_words:
        return ValidationResult(ok=True, errors=[])
    return ValidationResult(ok=False, errors=[f"word_count {wc} exceeds max_words {max_words}"])

