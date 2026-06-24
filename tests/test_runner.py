"""Runner Phase-A / Phase-B against the local SQLite store."""

from __future__ import annotations

import pytest

SITE = {
    "name": "Acme",
    "domain": "acme.example",
    "brand_voice": "Direct.",
    "custom_prompts": {},
    "image_style": None,
    "pillar_cluster_map": {},
    "internal_links": [],
    "discovery": {"source": "seed", "seed_topics": ["dpdpa"]},
}


def _seed_run(store, auto_approve=True) -> tuple[str, str]:
    site = store.create_site(SITE)
    run = store.create_run(
        site["id"],
        {
            "status": "queued",
            "stages": {},
            "input": {
                "topic": "DPDPA compliance checklist",
                "keyword": "dpdpa compliance checklist",
                "expert_insights": "We audited 40 firms.",
                "auto_approve": auto_approve,
            },
        },
    )
    return site["id"], run["id"]


@pytest.mark.asyncio
async def test_runner_auto_approve_completes(store_db, patched_runner):
    from blogsmith.runner import execute_run

    site_id, run_id = _seed_run(store_db, auto_approve=True)
    await execute_run(site_id, run_id)

    data = store_db.get_run(site_id, run_id)
    assert data["status"] == "done"
    assert "distribution" in data["stages"]
    assert data["stages"]["final"]["title"].startswith("DPDPA")


@pytest.mark.asyncio
async def test_runner_pauses_then_resumes(store_db, patched_runner):
    from blogsmith.runner import execute_resume, execute_run

    site_id, run_id = _seed_run(store_db, auto_approve=False)
    await execute_run(site_id, run_id)
    data = store_db.get_run(site_id, run_id)
    assert data["status"] == "awaiting_expert"
    assert "critique" in data["stages"]
    assert "final" not in data["stages"]

    status = await execute_resume(site_id, run_id, "approve")
    assert status == "done"
    data = store_db.get_run(site_id, run_id)
    assert data["stages"]["distribution"]["linkedin_thread"]


@pytest.mark.asyncio
async def test_runner_reject_stops(store_db, patched_runner):
    from blogsmith.runner import execute_resume, execute_run

    site_id, run_id = _seed_run(store_db, auto_approve=False)
    await execute_run(site_id, run_id)
    status = await execute_resume(site_id, run_id, "reject")
    assert status == "rejected"
    assert store_db.get_run(site_id, run_id)["status"] == "rejected"
