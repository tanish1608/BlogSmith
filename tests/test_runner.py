"""Email-gate tokens + runner Phase-A/Phase-B against the fake Firestore."""

from __future__ import annotations

import pytest

from tests.fakes import FakeImages, FakeLlm

SITE = {
    "domain": "acme.example",
    "brand_voice": "Direct.",
    "custom_prompts": {},
    "image_style": None,
    "pillar_cluster_map": {},
    "internal_links": [],
    "discovery": {"source": "seed", "seed_topics": ["dpdpa"]},
}


def _seed_run(uid="u1", site_id="s1", run_id="r1", auto_approve=True):
    from blogsmith.firestore_db import run_doc, site_doc, user_doc

    user_doc(uid).set({"email": "owner@acme.example", "keys": {}})
    site_doc(uid, site_id).set(SITE)
    run_doc(uid, site_id, run_id).set(
        {
            "status": "queued",
            "stages": {},
            "input": {
                "topic": "DPDPA compliance checklist",
                "keyword": "dpdpa compliance checklist",
                "expert_insights": "We audited 40 firms.",
                "auto_approve": auto_approve,
            },
        }
    )


@pytest.fixture
def patched_runner(monkeypatch):
    monkeypatch.setattr("blogsmith.runner.LlmClient", lambda *a, **k: FakeLlm())
    monkeypatch.setattr("blogsmith.runner.ImageClient", lambda *a, **k: FakeImages())


@pytest.mark.asyncio
async def test_runner_auto_approve_completes(fake_db, patched_runner):
    from blogsmith.firestore_db import run_doc
    from blogsmith.runner import execute_run

    _seed_run(auto_approve=True)
    await execute_run("u1", "s1", "r1")

    data = run_doc("u1", "s1", "r1").get().to_dict()
    assert data["status"] == "done"
    assert "distribution" in data["stages"]
    assert data["title"].startswith("DPDPA")


@pytest.mark.asyncio
async def test_runner_pauses_then_resumes(fake_db, patched_runner):
    from blogsmith.firestore_db import run_doc
    from blogsmith.runner import execute_resume, execute_run

    _seed_run(auto_approve=False)
    await execute_run("u1", "s1", "r1")
    data = run_doc("u1", "s1", "r1").get().to_dict()
    assert data["status"] == "awaiting_expert"
    assert "critique" in data["stages"]
    assert "final" not in data["stages"]

    status = await execute_resume("u1", "s1", "r1", "approve")
    assert status == "done"
    data = run_doc("u1", "s1", "r1").get().to_dict()
    assert data["stages"]["distribution"]["linkedin_thread"]


@pytest.mark.asyncio
async def test_runner_reject_stops(fake_db, patched_runner):
    from blogsmith.firestore_db import run_doc
    from blogsmith.runner import execute_resume, execute_run

    _seed_run(auto_approve=False)
    await execute_run("u1", "s1", "r1")
    status = await execute_resume("u1", "s1", "r1", "reject")
    assert status == "rejected"
    assert run_doc("u1", "s1", "r1").get().to_dict()["status"] == "rejected"
