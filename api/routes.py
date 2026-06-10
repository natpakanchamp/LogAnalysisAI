"""JSON API for the HITL dashboard. All responses use a consistent envelope."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from api.state import state
from loganalysis.feedback.store import ACCEPT, REJECT

router = APIRouter(prefix="/api")


def ok(data: Any) -> dict:
    return {"success": True, "data": data, "error": None}


def err(message: str) -> dict:
    return {"success": False, "data": None, "error": message}


class FeedbackIn(BaseModel):
    alert_id: str
    decision: str
    reviewer: str = "on-call"
    note: str = ""

    @field_validator("decision")
    @classmethod
    def _valid(cls, v: str) -> str:
        if v not in {ACCEPT, REJECT}:
            raise ValueError(f"decision must be '{ACCEPT}' or '{REJECT}'")
        return v


@router.get("/alerts")
def list_alerts(flagged: bool | None = None) -> dict:
    alerts = state.alerts
    if flagged is not None:
        alerts = [a for a in alerts if a["flagged_for_review"] == flagged]
    reviewed = {fb.alert_id: fb.decision for fb in state.feedback.all()}
    enriched = [{**a, "review_decision": reviewed.get(a["alert_id"])} for a in alerts]
    return ok(enriched)


@router.get("/stats")
def stats() -> dict:
    return ok(state.stats())


@router.post("/feedback")
def submit_feedback(body: FeedbackIn) -> dict:
    if body.alert_id not in state.alerts_by_id:
        return err(f"unknown alert_id '{body.alert_id}'")
    session = state.sessions_by_alert.get(body.alert_id)
    record = state.feedback.record(
        alert_id=body.alert_id,
        session_id=getattr(session, "session_id", body.alert_id),
        decision=body.decision, reviewer=body.reviewer, note=body.note,
    )
    return ok({"alert_id": record.alert_id, "decision": record.decision})


@router.post("/alerts/{alert_id}/explain")
def explain(alert_id: str) -> dict:
    try:
        summary = state.explain(alert_id)
    except KeyError:
        return err(f"unknown alert_id '{alert_id}'")
    return ok({"alert_id": alert_id, "summary": summary, "llm_enabled": state.llm.uses_llm})
