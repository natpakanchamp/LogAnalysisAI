"""Dashboard API smoke tests (require a trained bundle + sample dataset)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loganalysis.config import settings
from loganalysis.persistence import BUNDLE_NAME

_HAS_BUNDLE = settings.artifact_path(BUNDLE_NAME).exists()
_HAS_DATA = (settings.dataset_dir("sample") / "logs.jsonl").exists()
pytestmark = pytest.mark.skipif(
    not (_HAS_BUNDLE and _HAS_DATA),
    reason="needs trained bundle + sample dataset (run download_data + train)",
)


@pytest.fixture(scope="module")
def client():
    from api.main import app

    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["alerts_loaded"] is True


def test_stats_envelope(client):
    r = client.get("/api/stats")
    body = r.json()
    assert body["success"] is True
    assert body["data"]["total_alerts"] > 0


def test_alerts_feed_and_filter(client):
    all_alerts = client.get("/api/alerts").json()["data"]
    flagged = client.get("/api/alerts?flagged=true").json()["data"]
    assert len(all_alerts) > 0
    assert all(a["flagged_for_review"] for a in flagged)
    # Every alert carries a severity and a summary.
    assert all(a["severity"] and a["summary"] for a in all_alerts)


def test_feedback_roundtrip(client):
    alert_id = client.get("/api/alerts").json()["data"][0]["alert_id"]
    r = client.post("/api/feedback", json={"alert_id": alert_id, "decision": "accept"})
    assert r.json()["success"] is True


def test_feedback_rejects_bad_decision(client):
    alert_id = client.get("/api/alerts").json()["data"][0]["alert_id"]
    r = client.post("/api/feedback", json={"alert_id": alert_id, "decision": "nope"})
    assert r.status_code == 422  # pydantic validation error


def test_explain_returns_summary(client):
    alert_id = client.get("/api/alerts").json()["data"][0]["alert_id"]
    r = client.post(f"/api/alerts/{alert_id}/explain")
    body = r.json()
    assert body["success"] is True
    assert isinstance(body["data"]["summary"], str) and body["data"]["summary"]
