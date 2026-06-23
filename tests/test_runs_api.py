"""HTTP flow: create site → create run → pipeline completes → fetch result.

The scheduler tick fan-out is tested with all_sites/dispatch patched to the fake DB.
"""

from __future__ import annotations

import pytest

from blogsmith.config import get_settings
from tests.fakes import FakeImages, FakeLlm


@pytest.fixture
def patched_runner(monkeypatch):
    monkeypatch.setattr("blogsmith.runner.LlmClient", lambda *a, **k: FakeLlm())
    monkeypatch.setattr("blogsmith.runner.ImageClient", lambda *a, **k: FakeImages())


def _make_site(client) -> str:
    r = client.post("/sites", json={
        "name": "Acme", "domain": "acme.example",
        "discovery": {"source": "seed", "seed_topics": ["dpdpa compliance"]},
    })
    assert r.status_code == 201
    return r.json()["id"]


def test_create_run_executes_and_returns_result(client, patched_runner):
    site_id = _make_site(client)

    r = client.post(f"/sites/{site_id}/runs", json={
        "topic": "DPDPA compliance checklist",
        "keyword": "dpdpa compliance checklist",
        "auto_approve": True,
    })
    assert r.status_code == 202
    run_id = r.json()["id"]

    # Background task runs during the TestClient request cycle → run completes.
    r = client.get(f"/sites/{site_id}/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    r = client.get(f"/sites/{site_id}/runs/{run_id}/result")
    assert r.status_code == 200
    result = r.json()
    assert result["title"].startswith("DPDPA")
    assert result["markdown"] and "[[IMAGE:" not in result["markdown"]
    assert len(result["linkedin_thread"]) >= 2


def test_review_gate_decision_resumes_run(client, patched_runner):
    site_id = _make_site(client)
    r = client.post(f"/sites/{site_id}/runs", json={
        "topic": "DPDPA compliance checklist",
        "keyword": "dpdpa compliance checklist",
        "auto_approve": False,
    })
    run_id = r.json()["id"]

    # Phase A ran in the background → paused at the review gate.
    assert client.get(f"/sites/{site_id}/runs/{run_id}").json()["status"] == "awaiting_expert"

    # Approve from the dashboard → resumes to done.
    r = client.post(f"/sites/{site_id}/runs/{run_id}/decision", json={"decision": "approve"})
    assert r.status_code == 202
    assert client.get(f"/sites/{site_id}/runs/{run_id}").json()["status"] == "done"


def test_decision_rejected_when_not_awaiting(client, patched_runner):
    site_id = _make_site(client)
    r = client.post(f"/sites/{site_id}/runs", json={"topic": "x", "auto_approve": True})
    run_id = r.json()["id"]  # auto-approve → already done, not awaiting
    r = client.post(f"/sites/{site_id}/runs/{run_id}/decision", json={"decision": "approve"})
    assert r.status_code == 409


def test_scheduler_tick_fans_out(client, fake_db, monkeypatch):
    site_id = _make_site(client)
    # Enable a daily slot that's already past today.
    client.patch(f"/sites/{site_id}", json={
        "schedule": {"enabled": True, "cadence": "daily", "times": ["00:01"],
                     "timezone": "UTC", "count_per_run": 3},
    })

    # Scan the fake DB (no collection-group support) + don't actually execute runs.
    def fake_all_sites():
        from blogsmith.firestore_db import sites_col
        for snap in sites_col("dev-user").stream():
            yield "dev-user", snap.id, snap.to_dict()

    monkeypatch.setattr("blogsmith.firestore_db.all_sites", fake_all_sites)
    monkeypatch.setattr("blogsmith.api.routers.scheduler.dispatch_run", lambda *a, **k: "noop")

    secret = get_settings().scheduler_secret
    r = client.post("/scheduler/tick", headers={"X-Scheduler-Secret": secret})
    assert r.status_code == 200
    assert r.json()["enqueued"] == 3

    # A second tick the same day must not refire the slot.
    r = client.post("/scheduler/tick", headers={"X-Scheduler-Secret": secret})
    assert r.json()["enqueued"] == 0


def test_scheduler_tick_rejects_bad_secret(client):
    r = client.post("/scheduler/tick", headers={"X-Scheduler-Secret": "wrong"})
    assert r.status_code == 403
