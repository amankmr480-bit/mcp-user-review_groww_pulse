"""
Phase 5 orchestration helpers:
- run Phase 1/2/3
- send Phase 3 draft email
- load generated artifacts for API/UI
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from config import PHASE1_DIR, PHASE2_DIR, PHASE3_DIR, PHASE1_INPUT_CSV


def week_info_from_date(date_str: str) -> dict[str, str]:
    """
    Map a calendar day (YYYY-MM-DD) to ISO week id used by Phase 1–3 files
    (e.g. 2026-W11) and the ISO week Monday as week_beginning (YYYY-MM-DD).
    """
    s = (date_str or "").strip()
    if not s:
        raise ValueError("date is empty")
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError("date must be YYYY-MM-DD") from e
    y, w, _ = dt.isocalendar()
    week_id = f"{y}-W{w:02d}"
    monday = date.fromisocalendar(y, w, 1)
    return {
        "week_id": week_id,
        "week_beginning": monday.isoformat(),
        "date": s,
    }


def resolve_week_id(week: Optional[str], week_start_date: Optional[str]) -> Optional[str]:
    """Prefer week_start_date (YYYY-MM-DD) over legacy week id string."""
    if week_start_date and str(week_start_date).strip():
        return week_info_from_date(str(week_start_date).strip())["week_id"]
    if week and str(week).strip():
        return str(week).strip()
    return None


def week_info_from_week_id(week_id: str) -> dict[str, str]:
    """Normalize e.g. 2026-W11 and return ISO week Monday as week_beginning."""
    s = (week_id or "").strip()
    m = re.match(r"^(\d{4})-W(\d{1,2})$", s, re.IGNORECASE)
    if not m:
        raise ValueError("week_id must look like 2026-W11")
    y, w = int(m.group(1)), int(m.group(2))
    if w < 1 or w > 53:
        raise ValueError("invalid ISO week number")
    try:
        monday = date.fromisocalendar(y, w, 1)
    except ValueError as e:
        raise ValueError("invalid ISO week for that year") from e
    norm = f"{y}-W{w:02d}"
    return {"week_id": norm, "week_beginning": monday.isoformat()}


def _run_python(script: Path, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(script)] + args
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def run_phase1(*, input_csv: str = PHASE1_INPUT_CSV) -> dict[str, Any]:
    result = _run_python(PHASE1_DIR / "ingest.py", ["--input", input_csv], cwd=PHASE1_DIR)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_phase2(*, week: Optional[str] = None, batch_size: Optional[int] = None) -> dict[str, Any]:
    args: list[str] = []
    if week:
        args += ["--week", week]
    env = None
    if batch_size:
        env = {"PHASE2_REVIEW_BATCH_SIZE": str(batch_size)}
    cmd = [sys.executable, str(PHASE2_DIR / "analyze.py")] + args
    merged_env = None
    if env is not None:
        import os

        merged_env = os.environ.copy()
        merged_env.update(env)
    result = subprocess.run(cmd, cwd=str(PHASE2_DIR), capture_output=True, text=True, env=merged_env)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_phase3(*, week: Optional[str] = None) -> dict[str, Any]:
    args: list[str] = []
    if week:
        args += ["--week", week]
    result = _run_python(PHASE3_DIR / "generate_notes.py", args, cwd=PHASE3_DIR)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def send_email(week: str) -> dict[str, Any]:
    result = _run_python(PHASE3_DIR / "send_email.py", ["--week", week], cwd=PHASE3_DIR)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON object in {path}")
    return data


def list_weeks() -> list[str]:
    out = PHASE3_DIR / "output"
    if not out.exists():
        return []
    weeks: list[str] = []
    for p in sorted(out.glob("weekly_note_*.json")):
        week = p.stem.replace("weekly_note_", "")
        if week:
            weeks.append(week)
    return weeks


def get_note(week: str) -> dict[str, Any]:
    return _read_json(PHASE3_DIR / "output" / f"weekly_note_{week}.json")


def get_email_draft(week: str) -> dict[str, Any]:
    return _read_json(PHASE3_DIR / "output" / f"email_draft_{week}.json")


def run_pipeline(
    *,
    week: Optional[str],
    run_ingest: bool,
    batch_size: Optional[int],
    week_start_date: Optional[str] = None,
) -> dict[str, Any]:
    resolved = resolve_week_id(week, week_start_date)
    steps: dict[str, Any] = {}
    if run_ingest:
        steps["phase1"] = run_phase1()
        if not steps["phase1"]["ok"]:
            return {"ok": False, "resolved_week_id": resolved, "steps": steps}

    steps["phase2"] = run_phase2(week=resolved, batch_size=batch_size)
    if not steps["phase2"]["ok"]:
        return {"ok": False, "resolved_week_id": resolved, "steps": steps}

    steps["phase3"] = run_phase3(week=resolved)
    if not steps["phase3"]["ok"]:
        return {"ok": False, "resolved_week_id": resolved, "steps": steps}

    return {"ok": True, "resolved_week_id": resolved, "steps": steps}

