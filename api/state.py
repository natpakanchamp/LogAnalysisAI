"""In-memory dashboard state: builds the alert feed and holds the feedback store.

On load it runs the trained pipeline over the held-out test split (the same split used by
evaluation) to produce a realistic alert feed. A small deterministic subset of sessions has
its heartbeat marked "missed" so the dashboard also demonstrates the deadlock HITL trigger.
"""

from __future__ import annotations

from dataclasses import dataclass

from loganalysis.config import settings
from loganalysis.datasplit import split_sessions
from loganalysis.feedback.store import FeedbackStore
from loganalysis.ingestion.loader import load_dataset
from loganalysis.persistence import BUNDLE_NAME
from loganalysis.pipeline import Pipeline
from loganalysis.scoring.severity import severity_rank
from loganalysis.summarize.llm_summarizer import Summarizer


@dataclass
class DashboardState:
    dataset: str = "sample"
    loaded: bool = False

    def __post_init__(self) -> None:
        self.alerts: list[dict] = []
        self.alerts_by_id: dict[str, dict] = {}
        self.sessions_by_alert: dict[str, object] = {}
        self.feedback = FeedbackStore(settings.data_dir / "feedback.jsonl")
        self.llm = Summarizer()  # may use Gemini on demand for /explain
        self._pipeline: Pipeline | None = None

    def load(self) -> None:
        bundle = settings.artifact_path(BUNDLE_NAME)
        if not bundle.exists():
            raise FileNotFoundError(
                f"No trained bundle at {bundle}. Run scripts/train.py first."
            )
        # Feed uses the fast template summarizer; the LLM is reserved for on-demand /explain.
        self._pipeline = Pipeline.from_bundle(bundle, summarizer=Summarizer(api_key=""))
        sessions = load_dataset(self.dataset, settings.dataset_dir(self.dataset))
        _train, test = split_sessions(sessions)

        # Mark every 23rd session as a missed heartbeat to surface the deadlock trigger.
        alerts: list[dict] = []
        for i, session in enumerate(test):
            heartbeat_ok = (i % 23 != 0)
            result = self._pipeline.process_session(session, heartbeat_ok=heartbeat_ok)
            if result.alert is None:
                continue
            payload = result.alert.to_dict()
            payload["ground_truth"] = session.label
            alerts.append(payload)
            self.sessions_by_alert[result.alert.alert_id] = session

        alerts.sort(
            key=lambda a: (a["flagged_for_review"], severity_rank(a["severity"]), a["confidence"]),
            reverse=True,
        )
        self.alerts = alerts
        self.alerts_by_id = {a["alert_id"]: a for a in alerts}
        self.loaded = True

    def stats(self) -> dict:
        by_severity: dict[str, int] = {}
        for a in self.alerts:
            by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1
        flagged = sum(1 for a in self.alerts if a["flagged_for_review"])
        ai_only = sum(1 for a in self.alerts if a["rule_vs_ai_conflict"] and "deeplog" in a["detectors"])
        reviewed = {fb.alert_id for fb in self.feedback.all()}
        return {
            "total_alerts": len(self.alerts),
            "flagged_for_review": flagged,
            "by_severity": by_severity,
            "ai_only_catches": ai_only,
            "reviewed": len(reviewed & set(self.alerts_by_id)),
            "llm_enabled": self.llm.uses_llm,
        }

    def explain(self, alert_id: str) -> str:
        """(Re)generate a root-cause summary for one alert using the LLM if available."""
        alert = self.alerts_by_id.get(alert_id)
        if alert is None:
            raise KeyError(alert_id)
        summary = self.llm.summarize(
            category=alert["category"], severity=alert["severity"],
            suspect_service=alert["suspect_service"], suspect_commit=alert["suspect_commit"],
            sample_messages=list(alert["sample_messages"]), detectors=list(alert["detectors"]),
            anomaly_score=alert["anomaly_score"], confidence=alert["confidence"],
        )
        alert["summary"] = summary
        return summary


state = DashboardState()
