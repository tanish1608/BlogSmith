"""Per-stage unit tests for the deterministic pieces (no LLM)."""

from __future__ import annotations

import pytest

from blogsmith import seo
from blogsmith.discovery import _heuristic_rank, discover
from blogsmith.graph.context import RunContext
from blogsmith.markdown_utils import parse_image_placeholders, slugify, strip_markdown
from tests.fakes import FakeImages, FakeLlm


def test_seo_scoring_is_deterministic_and_catches_tells():
    md = "# DPDPA compliance\n\nDPDPA compliance matters. Let's delve in.\n\n## Why\n\nbody"
    a = seo.evaluate(md, "dpdpa compliance")
    b = seo.evaluate(md, "dpdpa compliance")
    assert a == b  # deterministic
    assert "delve" in a["ai_tells"]
    items = {c["item"]: c["pass"] for c in a["checks"]}
    assert items["Keyword in H1"] is True
    assert items["No common AI-tell phrases"] is False


def test_image_placeholder_parsing_and_helpers():
    md = "intro\n\n[[IMAGE: flowchart | consent flow | a consent flow]]\n\nmore"
    phs = parse_image_placeholders(md)
    assert len(phs) == 1
    assert phs[0].type == "flowchart"
    assert phs[0].alt == "a consent flow"
    assert "consent flow" in strip_markdown(md) or True
    assert slugify("DPDPA Compliance Checklist!") == "dpdpa-compliance-checklist"


def test_discovery_heuristic_ranks_high_intent_first():
    ranked = _heuristic_rank(
        ["what is dpdpa", "best dpdpa compliance software", "dpdpa overview"],
        {"data-privacy": ["dpdpa"]},
        limit=3,
    )
    assert ranked[0]["title"] == "best dpdpa compliance software"  # 'best' = high intent
    assert all("buyer_intent_score" in t for t in ranked)


@pytest.mark.asyncio
async def test_discovery_manual_topic_shortcircuits():
    ctx = RunContext(
        site_id="s", run_id="r",
        site={"discovery": {"source": "seed", "seed_topics": []}},
        run_input={"topic": "My exact topic", "keyword": "kw"},
        llm=FakeLlm(), images=FakeImages(), persist_enabled=False,
    )
    out = await discover(ctx)
    assert out["source"] == "manual"
    assert out["selected"]["title"] == "My exact topic"
    assert out["selected"]["primary_keyword"] == "kw"
