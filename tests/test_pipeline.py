"""End-to-end pipeline test with fakes — auto-approve path through all 9 stages."""

from __future__ import annotations

import pytest

from blogsmith.graph.blog_graph import resume_pipeline, run_pipeline
from blogsmith.graph.context import RunContext
from blogsmith.models import RunStatus
from tests.fakes import FakeImages, FakeLlm

SITE = {
    "domain": "acme.example",
    "brand_voice": "Direct, expert, no fluff.",
    "custom_prompts": {"draft": "Cite the DPDPA section number."},
    "image_style": "clean minimal line art",
    "pillar_cluster_map": {"data-privacy": ["dpdpa", "consent"]},
    "internal_links": [],
    "discovery": {"source": "seed", "seed_topics": ["dpdpa compliance"]},
}


def _ctx(auto_approve: bool) -> RunContext:
    return RunContext(
        uid="u1", site_id="s1", run_id="r1", site=SITE,
        run_input={
            "topic": "DPDPA compliance checklist",
            "keyword": "dpdpa compliance checklist",
            "expert_insights": "In a 2025 audit we found 80% lacked a consent notice.",
            "auto_approve": auto_approve,
        },
        llm=FakeLlm(), images=FakeImages(), auto_approve=auto_approve,
        persist_enabled=False,
    )


@pytest.mark.asyncio
async def test_full_pipeline_auto_approve():
    state = await run_pipeline(_ctx(auto_approve=True))

    assert state["status"] == RunStatus.DONE.value
    for slice_name in ("discovery", "research", "outline", "draft", "critique",
                       "expert", "final", "visuals", "distribution"):
        assert slice_name in state, f"missing slice {slice_name}"

    # Image placeholder was replaced (Mermaid fallback since image gen is off).
    md = state["visuals"]["markdown"]
    assert "[[IMAGE:" not in md
    assert "```mermaid" in md

    # Publishable metadata + distribution present.
    assert state["final"]["title"].startswith("DPDPA")
    assert state["final"]["json_ld"]["@type"] == "BlogPosting"
    assert len(state["distribution"]["linkedin_thread"]) >= 2


@pytest.mark.asyncio
async def test_pipeline_pauses_at_gate_then_resumes():
    # Phase A without auto-approve → pauses at the email gate.
    state = await run_pipeline(_ctx(auto_approve=False))
    assert state["status"] == RunStatus.AWAITING_EXPERT.value
    assert "final" not in state  # did not proceed past the gate

    # Phase B: approve and resume from the reconstructed state.
    resumed = await resume_pipeline(_ctx(auto_approve=False), state, decision="approve")
    assert resumed["status"] == RunStatus.DONE.value
    assert resumed["final"]["slug"] == "dpdpa-compliance-checklist"
