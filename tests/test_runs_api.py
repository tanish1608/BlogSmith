"""HTTP flow: create site → create run → pipeline completes → fetch result.

Uses the shared ``client`` (temp SQLite) and ``patched_runner`` fixtures.
"""

from __future__ import annotations

from tests.conftest import wait_for_status


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

    # The run dispatches as a concurrent asyncio task → wait for it to finish.
    assert wait_for_status(client, site_id, run_id, "done") == "done"

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
    assert wait_for_status(client, site_id, run_id, "awaiting_expert") == "awaiting_expert"

    # Approve from the dashboard → resumes to done.
    r = client.post(f"/sites/{site_id}/runs/{run_id}/decision", json={"decision": "approve"})
    assert r.status_code == 202
    assert wait_for_status(client, site_id, run_id, "done") == "done"


def test_decision_rejected_when_not_awaiting(client, patched_runner):
    site_id = _make_site(client)
    r = client.post(f"/sites/{site_id}/runs", json={"topic": "x", "auto_approve": True})
    run_id = r.json()["id"]  # auto-approve → already done, not awaiting
    r = client.post(f"/sites/{site_id}/runs/{run_id}/decision", json={"decision": "approve"})
    assert r.status_code == 409


def test_scheduler_tick_fans_out(client, monkeypatch):
    site_id = _make_site(client)
    # Enable a daily slot that's already past today.
    client.patch(f"/sites/{site_id}", json={
        "schedule": {"enabled": True, "cadence": "daily", "times": ["00:01"],
                     "timezone": "UTC", "count_per_run": 3},
    })

    # Don't actually execute the queued runs.
    monkeypatch.setattr("blogsmith.scheduler_local.dispatch_run", lambda *a, **k: "noop")

    r = client.post("/scheduler/tick")
    assert r.status_code == 200
    assert r.json()["enqueued"] == 3

    # A second tick the same day must not refire the slot.
    r = client.post("/scheduler/tick")
    assert r.json()["enqueued"] == 0
