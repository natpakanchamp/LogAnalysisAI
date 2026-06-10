"""HITL trigger logic (PRD §05)."""

from loganalysis.alerting.hitl import (
    AI_RULE_CONFLICT,
    HEARTBEAT_DEADLOCK,
    LOW_CONFIDENCE,
    evaluate_hitl,
)


def test_low_confidence_triggers_review():
    d = evaluate_hitl(confidence=0.5, ai_anomaly=True, rule_anomaly=True, confidence_threshold=0.65)
    assert d.flagged is True
    assert LOW_CONFIDENCE in d.reasons


def test_ai_rule_conflict_triggers_review():
    # AI flags anomaly, rule does not -> conflict (the "AI catches what rules miss" case).
    d = evaluate_hitl(confidence=0.95, ai_anomaly=True, rule_anomaly=False, confidence_threshold=0.65)
    assert d.flagged is True
    assert AI_RULE_CONFLICT in d.reasons


def test_heartbeat_deadlock_triggers_review():
    # System hung (heartbeat missed), no error log (rule silent) -> deadlock signature.
    d = evaluate_hitl(
        confidence=0.95, ai_anomaly=False, rule_anomaly=False,
        heartbeat_ok=False, confidence_threshold=0.65,
    )
    assert d.flagged is True
    assert HEARTBEAT_DEADLOCK in d.reasons


def test_confident_agreement_is_not_flagged():
    d = evaluate_hitl(
        confidence=0.95, ai_anomaly=True, rule_anomaly=True,
        heartbeat_ok=True, confidence_threshold=0.65,
    )
    assert d.flagged is False
    assert d.reasons == ()


def test_multiple_reasons_accumulate():
    d = evaluate_hitl(confidence=0.3, ai_anomaly=True, rule_anomaly=False, confidence_threshold=0.65)
    assert LOW_CONFIDENCE in d.reasons and AI_RULE_CONFLICT in d.reasons
