"""
Phase 2: GROQ LLM analysis configuration.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    """Parse KEY=VALUE lines into os.environ if key not already set (stdlib fallback)."""
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
        key, _, val = s.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        existing = os.environ.get(key)
        if existing is not None and str(existing).strip():
            continue
        os.environ[key] = val


try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Fill missing or blank vars from .env (covers no python-dotenv, or empty placeholder in process env)
_load_env_file(BASE_DIR / ".env")

# Phase 1 weekly JSON files (default: sibling phase_1/output)
DEFAULT_INPUT_DIR = BASE_DIR.parent / "phase_1" / "output"
INPUT_DIR = os.environ.get("PHASE2_INPUT_DIR", str(DEFAULT_INPUT_DIR))
OUTPUT_DIR = os.environ.get("PHASE2_OUTPUT_DIR", str(BASE_DIR / "output"))

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = os.environ.get(
    "GROQ_API_URL",
    "https://api.groq.com/openai/v1/chat/completions",
)
# Widely available on Groq; override via env if needed
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# How many reviews to send in each "map" API call (2.1 batching)
REVIEW_BATCH_SIZE = max(1, int(os.environ.get("PHASE2_REVIEW_BATCH_SIZE", "25")))

MAX_RETRIES = int(os.environ.get("PHASE2_MAX_RETRIES", "5"))
INITIAL_BACKOFF_SEC = float(os.environ.get("PHASE2_INITIAL_BACKOFF_SEC", "1.0"))
