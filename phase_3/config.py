"""
Phase 3: note + email draft generation configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE parser fallback (used when python-dotenv isn't installed)."""
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip()
        if not k or not v:
            continue
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        existing = os.environ.get(k)
        # Treat blank/whitespace as unset so the .env value is applied even when
        # the process already has an empty placeholder.
        if existing is None or not str(existing).strip():
            os.environ[k] = v


try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

_load_env_file(BASE_DIR / ".env")


# Inputs from Phase 2
DEFAULT_INPUT_DIR = BASE_DIR.parent / "phase_2" / "output"
INPUT_DIR = os.environ.get("PHASE3_INPUT_DIR", str(DEFAULT_INPUT_DIR))

# Outputs for Phase 3
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR = os.environ.get("PHASE3_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))

# GROQ configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = os.environ.get(
    "GROQ_API_URL",
    "https://api.groq.com/openai/v1/chat/completions",
)
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# Email recipient (self/alias only)
ALIAS_EMAIL = os.environ.get("ALIAS_EMAIL", "")

# Note constraint
MAX_NOTE_WORDS = int(os.environ.get("PHASE3_MAX_NOTE_WORDS", "250"))

