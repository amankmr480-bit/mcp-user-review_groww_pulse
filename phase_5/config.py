"""
Phase 5 backend config.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

PHASE1_DIR = ROOT_DIR / "phase_1"
PHASE2_DIR = ROOT_DIR / "phase_2"
PHASE3_DIR = ROOT_DIR / "phase_3"

PHASE1_INPUT_CSV = os.environ.get("PHASE1_INPUT_CSV", str(PHASE1_DIR / "input" / "reviews.csv"))

# FastAPI host/port
API_HOST = os.environ.get("PHASE5_API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("PHASE5_API_PORT", "8000"))

