"""Human-in-the-Loop routing (PRD §05, Pattern 2: review flagged outputs only).

Triggers are objective and measurable, as the PRD requires:
* ``low_confidence``     — model confidence below the threshold (default 0.65)
* ``ai_rule_conflict``   — the AI and the rule baseline disagree on whether it's an anomaly
* ``heartbeat_deadlock`` — heartbeat says the system is hung but no error log was produced
"""

from __future__ import annotations

from dataclasses import dataclass

from loganalysis.config import settings

LOW_CONFIDENCE = "low_confidence"
AI_RULE_CONFLICT = "ai_rule_conflict"
HEARTBEAT_DEADLOCK = "heartbeat_deadlock"


@dataclass(frozen=True)
class HitlDecision:
    flagged: bool
    reasons: tuple[str, ...]


def evaluate_hitl(
    *,
    confidence: float,
    ai_anomaly: bool,
    rule_anomaly: bool,
    heartbeat_ok: bool = True,
    confidence_threshold: float | None = None,
) -> HitlDecision:
    threshold = (
        confidence_threshold if confidence_threshold is not None
        else settings.confidence_threshold
    )
    reasons: list[str] = []

    if confidence < threshold:
        reasons.append(LOW_CONFIDENCE)

    if ai_anomaly != rule_anomaly:
        reasons.append(AI_RULE_CONFLICT)

    # Deadlock signature: the system appears hung (heartbeat missed) yet nothing errored.
    if not heartbeat_ok and not rule_anomaly:
        reasons.append(HEARTBEAT_DEADLOCK)

    return HitlDecision(flagged=bool(reasons), reasons=tuple(reasons))
