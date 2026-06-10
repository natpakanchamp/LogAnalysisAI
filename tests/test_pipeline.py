"""Integration: a tiny end-to-end pipeline over labeled sessions."""

from loganalysis.classification.root_cause import RootCauseClassifier
from loganalysis.detection.deeplog import DeepLogDetector
from loganalysis.ingestion.loader import LabeledSession
from loganalysis.parsing.drain_parser import DrainParser
from loganalysis.pipeline import Pipeline
from loganalysis.records import LogRecord
from loganalysis.scoring.severity import assess_severity, is_high_severity
from loganalysis.summarize.llm_summarizer import Summarizer
from loganalysis.summarize.templates import template_summary


def _session(sid: str, messages: list[str], label: int, category: str) -> LabeledSession:
    recs = tuple(
        LogRecord(timestamp=float(i), service="db-proxy", session_id=sid, message=m, raw=m)
        for i, m in enumerate(messages)
    )
    return LabeledSession(session_id=sid, records=recs, label=label, category=category)


def _build_pipeline() -> Pipeline:
    parser = DrainParser()
    normal_msgs = [
        "Receiving block blk_1 src /10.0.0.1",
        "Received block blk_1 of size 100 from /10.0.0.1",
        "PacketResponder 0 for block blk_1 terminating",
        "Verification succeeded for blk_1",
    ]
    normal_seqs = []
    cats = []
    for n in range(30):
        seq = [parser.fit_line(m) for m in normal_msgs]
        normal_seqs.append(seq)
        cats.append("normal")
    parser.freeze()

    detector = DeepLogDetector(num_keys=parser.num_keys, window_size=2, num_candidates=1, epochs=30)
    detector.fit(normal_seqs)
    clf = RootCauseClassifier(num_keys=parser.num_keys)
    clf.fit(normal_seqs, cats)
    # Force the offline template summarizer (no network in tests).
    return Pipeline(parser, detector, clf, summarizer=Summarizer(api_key=""))


def test_pipeline_redacts_and_produces_no_alert_for_normal():
    pipe = _build_pipeline()
    session = _session("blk_ok", [
        "Receiving block blk_9 src /10.0.0.2 token=ghp_secret123",
        "Received block blk_9 of size 200 from /10.0.0.2",
        "PacketResponder 0 for block blk_9 terminating",
        "Verification succeeded for blk_9",
    ], label=0, category="normal")

    result = pipe.process_session(session)
    assert result.ai_anomaly is False
    assert result.alert is None  # normal + heartbeat ok -> no alert


def test_pipeline_alerts_on_error_session_with_redaction_and_summary():
    pipe = _build_pipeline()
    session = _session("blk_bad", [
        "Receiving block blk_5 src /10.0.0.3",
        "ERROR DataNode exception on blk_5: connection reset password=hunter2",
    ], label=1, category="io_error")

    result = pipe.process_session(session)
    assert result.alert is not None
    alert = result.alert
    # Rule baseline catches the error keyword.
    assert "rule_based" in alert.detectors
    # Secret was redacted before the model and recorded for the audit trail.
    assert "credential_kv" in alert.redaction_categories
    assert all("hunter2" not in m for m in alert.sample_messages)
    assert alert.summary  # template summary produced


def test_pipeline_heartbeat_deadlock_creates_flagged_alert():
    pipe = _build_pipeline()
    # Perfectly normal logs, but heartbeat missed -> deadlock HITL trigger.
    session = _session("blk_hang", [
        "Receiving block blk_7 src /10.0.0.4",
        "Received block blk_7 of size 50 from /10.0.0.4",
        "Verification succeeded for blk_7",
    ], label=1, category="deadlock")

    result = pipe.process_session(session, heartbeat_ok=False)
    assert result.alert is not None
    assert result.alert.flagged_for_review is True
    assert "heartbeat_deadlock" in result.alert.flag_reasons


def test_template_summary_and_severity_helpers():
    text = template_summary(
        category="deadlock", severity="critical", suspect_service="worker",
        suspect_commit="abc1234", sample_messages=["FATAL deadlock detected"],
        detectors=["deeplog"],
    )
    assert "worker" in text and "CRITICAL" in text
    assert is_high_severity(assess_severity("deadlock", 0.95, True)) is True
    assert is_high_severity(assess_severity("latency", 0.2, False)) is False
