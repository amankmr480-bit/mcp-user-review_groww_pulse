"""
Phase 5 optional REST API (FastAPI) for external clients or automation.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import (
    get_email_draft,
    get_note,
    list_weeks,
    run_pipeline,
    send_email,
    week_info_from_date,
    week_info_from_week_id,
)


app = FastAPI(title="GROWW Review AI Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],  # optional: local SPAs / tools calling this API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineRunRequest(BaseModel):
    """Use week_start_date (YYYY-MM-DD) for the week containing that day, or legacy week id."""
    week: Optional[str] = None
    week_start_date: Optional[str] = None
    run_ingest: bool = False
    batch_size: Optional[int] = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/weeks")
def weeks() -> dict[str, list[str]]:
    return {"weeks": list_weeks()}


@app.get("/week/from-date")
def week_from_date(date: str = Query(..., description="Any calendar day in the target week, YYYY-MM-DD")) -> dict:
    try:
        return week_info_from_date(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/week/from-id")
def week_from_id(week_id: str = Query(..., description="ISO week id, e.g. 2026-W11")) -> dict:
    try:
        return week_info_from_week_id(week_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/weeks/{week}/note")
def week_note(week: str) -> dict:
    try:
        return get_note(week)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found for week {week}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weeks/{week}/email-draft")
def week_draft(week: str) -> dict:
    try:
        return get_email_draft(week)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Draft not found for week {week}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/run")
def pipeline_run(req: PipelineRunRequest) -> dict:
    result = run_pipeline(
        week=req.week,
        week_start_date=req.week_start_date,
        run_ingest=req.run_ingest,
        batch_size=req.batch_size,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return result


@app.post("/weeks/{week}/send")
def send_week_email(week: str) -> dict:
    result = send_email(week)
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result)
    return result

