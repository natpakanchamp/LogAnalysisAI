"""Alert envelope emitted for an anomalous session."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Alert:
    alert_id: str
    timestamp: float
    session_id: str
    severity: str
    confidence: float
    anomaly_score: float
    category: str
    suspect_service: str
    suspect_commit: str
    summary: str
    detectors: tuple[str, ...]
    rule_vs_ai_conflict: bool
    high_severity: bool
    flagged_for_review: bool
    flag_reasons: tuple[str, ...] = field(default_factory=tuple)
    sample_messages: tuple[str, ...] = field(default_factory=tuple)
    redaction_categories: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)
