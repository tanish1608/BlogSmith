"""Prompt assembly + authored-default integrity."""

from __future__ import annotations

import pytest

from blogsmith.models import Stage
from blogsmith.prompts import build_system_prompt
from blogsmith.prompts.defaults import STAGE_DEFAULTS, WRITING_STAGES


def test_every_pipeline_stage_has_a_default_prompt():
    # All stages except the human gate (expert), final-output containers (final/visuals
    # are 'finalize'/'visuals' keys) map to a default. Verify the LLM stages exist.
    expected = {"discovery", "research", "outline", "draft", "critique", "finalize", "visuals", "distribute"}
    assert expected == set(STAGE_DEFAULTS)


def test_writing_stages_get_human_like_rules():
    p = build_system_prompt("draft", brand_voice=None, custom=None)
    assert "WRITE LIKE A SHARP HUMAN EXPERT" in p
    assert '"delve"' in p  # the banned-phrase rule is present


def test_non_writing_stage_omits_human_like_rules():
    p = build_system_prompt("finalize")
    assert "WRITE LIKE A SHARP HUMAN EXPERT" not in p


def test_brand_voice_and_custom_are_layered():
    p = build_system_prompt(
        "draft",
        brand_voice="Wry, contrarian, technical.",
        custom="Always reference the DPDPA section number.",
    )
    assert "Wry, contrarian, technical." in p
    assert "DPDPA section number" in p
    # Base default still present and comes first.
    assert p.startswith(STAGE_DEFAULTS["draft"].strip())


def test_unknown_stage_raises():
    with pytest.raises(KeyError):
        build_system_prompt("nonsense")


def test_stage_enum_keys_align_with_defaults():
    # Stage enum's writing-ish stages should be representable in defaults.
    for s in ("draft", "critique", "distribute"):
        assert s in WRITING_STAGES
    assert Stage.DRAFT.value == "draft"
