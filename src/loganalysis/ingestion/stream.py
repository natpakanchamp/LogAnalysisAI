"""Replay loaded sessions as a simulated real-time stream.

The PRD calls for real-time ingestion; for the prototype we replay sessions in timestamp
order. ``replay_sessions`` yields whole sessions (the unit the pipeline scores), optionally
throttled to emulate wall-clock arrival.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from loganalysis.ingestion.loader import LabeledSession


def replay_sessions(
    sessions: list[LabeledSession], speed: float = 0.0
) -> Iterator[LabeledSession]:
    """Yield sessions in order.

    ``speed`` > 0 sleeps proportionally to each session's span (1.0 = real time, 60 = 60x
    faster). ``speed`` == 0 yields immediately (used by batch evaluation and tests).
    """
    ordered = sorted(sessions, key=lambda s: s.records[0].timestamp if s.records else 0.0)
    prev_end: float | None = None
    for session in ordered:
        if speed > 0 and prev_end is not None and session.records:
            gap = session.records[0].timestamp - prev_end
            if gap > 0:
                time.sleep(min(gap / speed, 2.0))
        yield session
        if session.records:
            prev_end = session.records[-1].timestamp
