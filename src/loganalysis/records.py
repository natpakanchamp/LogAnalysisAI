"""Shared, immutable data records used across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LogRecord:
    """A single ingested log line, normalized across services."""

    timestamp: float       # epoch seconds
    service: str           # emitting microservice
    session_id: str        # correlation key (e.g. HDFS block id)
    message: str           # log message body (post-redaction when stored)
    raw: str = ""          # original line as received
