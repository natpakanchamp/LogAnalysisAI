"""Append-only feedback store (PRD §05 feedback loop, §06 audit trail).

Engineer accept/reject decisions on flagged alerts are persisted as JSONL so they can later
seed retraining and provide an audit trail of every human action.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

ACCEPT = "accept"   # confirmed a real incident
REJECT = "reject"   # false positive
_VALID = {ACCEPT, REJECT}


@dataclass(frozen=True)
class FeedbackRecord:
    alert_id: str
    session_id: str
    decision: str
    reviewer: str
    timestamp: float
    note: str = ""


class FeedbackStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self, *, alert_id: str, session_id: str, decision: str,
        reviewer: str, note: str = "", timestamp: float | None = None,
    ) -> FeedbackRecord:
        if decision not in _VALID:
            raise ValueError(f"decision must be one of {sorted(_VALID)}, got {decision!r}")
        fb = FeedbackRecord(
            alert_id=alert_id, session_id=session_id, decision=decision,
            reviewer=reviewer, timestamp=timestamp if timestamp is not None else time.time(),
            note=note,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(fb)) + "\n")
        return fb

    def all(self) -> list[FeedbackRecord]:
        if not self.path.exists():
            return []
        records: list[FeedbackRecord] = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(FeedbackRecord(**json.loads(line)))
        return records

    def for_alert(self, alert_id: str) -> list[FeedbackRecord]:
        return [r for r in self.all() if r.alert_id == alert_id]
