"""End-to-end orchestration: redact → parse → detect → classify → score → summarize → alert.

The pipeline always returns a :class:`ProcessResult` (so evaluation can read predictions for
every session) and attaches an :class:`Alert` only when the session is anomalous or routed
to a human.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from loganalysis.alerting.alert import Alert
from loganalysis.alerting.hitl import evaluate_hitl
from loganalysis.classification.root_cause import RootCauseClassifier
from loganalysis.detection.base import DetectionResult
from loganalysis.detection.deeplog import DeepLogDetector
from loganalysis.detection.rule_based import RuleBasedDetector
from loganalysis.ingestion.loader import LabeledSession
from loganalysis.parsing.drain_parser import DrainParser
from loganalysis.persistence import load_bundle
from loganalysis.redaction.redactor import Redactor
from loganalysis.scoring.severity import assess_severity, is_high_severity
from loganalysis.summarize.llm_summarizer import Summarizer

CommitLookup = Callable[[str], str]
_DEFAULT_ANOMALY_CATEGORY = "abnormal_sequence"


@dataclass(frozen=True)
class ProcessResult:
    session_id: str
    ai_anomaly: bool
    rule_anomaly: bool
    anomaly_score: float
    confidence: float
    category: str
    severity: str
    high_severity: bool
    detect_latency: int | None     # first flagged window index (for MTTD), else None
    alert: Alert | None


class Pipeline:
    def __init__(
        self,
        parser: DrainParser,
        detector: DeepLogDetector,
        classifier: RootCauseClassifier,
        redactor: Redactor | None = None,
        summarizer: Summarizer | None = None,
        rule_detector: RuleBasedDetector | None = None,
        commit_lookup: CommitLookup | None = None,
    ) -> None:
        self.parser = parser
        self.detector = detector
        self.classifier = classifier
        self.redactor = redactor or Redactor()
        self.summarizer = summarizer or Summarizer()
        self.rule_detector = rule_detector or RuleBasedDetector()
        self.commit_lookup = commit_lookup

    @classmethod
    def from_bundle(cls, path: Path, **kwargs) -> "Pipeline":
        parser, detector, classifier = load_bundle(path)
        return cls(parser, detector, classifier, **kwargs)

    def process_session(
        self, session: LabeledSession, heartbeat_ok: bool = True
    ) -> ProcessResult:
        # 1. Redact every line before anything else touches it (PRD §03).
        redacted_messages: list[str] = []
        redaction_categories: set[str] = set()
        for rec in session.records:
            result = self.redactor.redact(rec.message)
            redacted_messages.append(result.text)
            redaction_categories.update(result.categories)

        # 2. Parse to event keys and run both detectors.
        keys = self.parser.transform(redacted_messages)
        ai: DetectionResult = self.detector.predict(keys)
        rule: DetectionResult = self.rule_detector.predict_messages(redacted_messages)

        # 3. Classify root cause; ensure an anomalous session never reports "normal".
        category, _clf_conf = self.classifier.predict(keys)
        if ai.is_anomaly and category == "normal":
            category = _DEFAULT_ANOMALY_CATEGORY

        # 4. Severity + high-severity gate.
        severity = assess_severity(category, ai.anomaly_score, rule.is_anomaly)
        high_sev = is_high_severity(severity)

        detect_latency = ai.anomalous_positions[0] if ai.anomalous_positions else None
        needs_alert = ai.is_anomaly or rule.is_anomaly or not heartbeat_ok

        alert = None
        if needs_alert:
            alert = self._build_alert(
                session=session, ai=ai, rule=rule, category=category,
                severity=severity, high_sev=high_sev, heartbeat_ok=heartbeat_ok,
                redacted_messages=redacted_messages,
                redaction_categories=tuple(sorted(redaction_categories)),
            )

        return ProcessResult(
            session_id=session.session_id, ai_anomaly=ai.is_anomaly,
            rule_anomaly=rule.is_anomaly, anomaly_score=ai.anomaly_score,
            confidence=ai.confidence, category=category, severity=severity,
            high_severity=high_sev, detect_latency=detect_latency, alert=alert,
        )

    def _build_alert(
        self, *, session: LabeledSession, ai: DetectionResult, rule: DetectionResult,
        category: str, severity: str, high_sev: bool, heartbeat_ok: bool,
        redacted_messages: list[str], redaction_categories: tuple[str, ...],
    ) -> Alert:
        suspect_service = _dominant_service(session)
        suspect_commit = self.commit_lookup(session.session_id) if self.commit_lookup else ""
        detectors = tuple(
            name for name, fired in (("deeplog", ai.is_anomaly), ("rule_based", rule.is_anomaly))
            if fired
        )
        conflict = ai.is_anomaly != rule.is_anomaly

        hitl = evaluate_hitl(
            confidence=ai.confidence, ai_anomaly=ai.is_anomaly,
            rule_anomaly=rule.is_anomaly, heartbeat_ok=heartbeat_ok,
        )

        # Surface the most relevant evidence lines (flagged windows / error lines first).
        evidence = _evidence_lines(redacted_messages, ai, rule)
        summary = self.summarizer.summarize(
            category=category, severity=severity, suspect_service=suspect_service,
            suspect_commit=suspect_commit, sample_messages=evidence,
            detectors=list(detectors), anomaly_score=ai.anomaly_score, confidence=ai.confidence,
        )

        ts = session.records[0].timestamp if session.records else 0.0
        return Alert(
            alert_id=f"alert-{session.session_id}", timestamp=ts,
            session_id=session.session_id, severity=severity, confidence=ai.confidence,
            anomaly_score=ai.anomaly_score, category=category,
            suspect_service=suspect_service, suspect_commit=suspect_commit, summary=summary,
            detectors=detectors, rule_vs_ai_conflict=conflict, high_severity=high_sev,
            flagged_for_review=hitl.flagged, flag_reasons=hitl.reasons,
            sample_messages=tuple(evidence), redaction_categories=redaction_categories,
        )


def _dominant_service(session: LabeledSession) -> str:
    if not session.records:
        return "unknown"
    counts = Counter(r.service for r in session.records)
    return counts.most_common(1)[0][0]


def _evidence_lines(
    messages: list[str], ai: DetectionResult, rule: DetectionResult, limit: int = 5
) -> list[str]:
    """Prefer flagged windows and error lines, then fill with context."""
    idxs: list[int] = []
    for pos in list(rule.anomalous_positions) + list(ai.anomalous_positions):
        if 0 <= pos < len(messages) and pos not in idxs:
            idxs.append(pos)
    for i in range(len(messages)):
        if i not in idxs:
            idxs.append(i)
    return [messages[i] for i in idxs[:limit]]
