"""Alert envelope serialization and feedback store behavior."""

import pytest

from loganalysis.alerting.alert import Alert
from loganalysis.feedback.store import ACCEPT, REJECT, FeedbackStore


def _alert() -> Alert:
    return Alert(
        alert_id="a1", timestamp=1.0, session_id="blk_1", severity="high",
        confidence=0.8, anomaly_score=0.9, category="io_error",
        suspect_service="db-proxy", suspect_commit="abc123", summary="boom",
        detectors=("deeplog",), rule_vs_ai_conflict=True, high_severity=True,
        flagged_for_review=True, flag_reasons=("ai_rule_conflict",),
        sample_messages=("ERROR ...",), redaction_categories=("credential_kv",),
    )


def test_alert_to_dict_roundtrips_fields():
    d = _alert().to_dict()
    assert d["alert_id"] == "a1"
    assert d["severity"] == "high"
    assert d["flag_reasons"] == ("ai_rule_conflict",)
    assert d["high_severity"] is True


def test_feedback_store_appends_and_reads(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.record(alert_id="a1", session_id="blk_1", decision=ACCEPT, reviewer="sre", timestamp=1.0)
    store.record(alert_id="a1", session_id="blk_1", decision=REJECT, reviewer="sre2", timestamp=2.0)

    all_fb = store.all()
    assert len(all_fb) == 2
    assert store.for_alert("a1")[0].decision == ACCEPT


def test_feedback_rejects_invalid_decision(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    with pytest.raises(ValueError):
        store.record(alert_id="a1", session_id="blk_1", decision="maybe", reviewer="sre")
