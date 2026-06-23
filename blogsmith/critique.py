"""Stage 5 — Critique.

A ruthless editor pass: tighten prose, kill AI tells, flag every claim
verified/unverified, and run the SEO checklist. The model does the editorial
work; :mod:`blogsmith.seo` adds the deterministic score so quality measurement
never depends on LLM availability.
"""

from __future__ import annotations

import json
import logging

from blogsmith import seo
from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.prompts import build_system_prompt
from blogsmith.prompts.defaults import SEO_CHECKLIST

logger = logging.getLogger(__name__)


async def critique(ctx: RunContext, draft_markdown: str, research_data: dict, keyword: str | None) -> dict:
    # Deterministic SEO is always computed (on the pre-edit draft as a baseline).
    base_seo = seo.evaluate(draft_markdown, keyword)

    if not ctx.llm.available:
        return {
            "edited_markdown": draft_markdown,
            "claims": [],
            "ai_tells_found": base_seo["ai_tells"],
            "fluff_removed": "skipped (no model available)",
            "checklist": base_seo["checks"],
            "seo": base_seo,
            "degraded": True,
        }

    system = build_system_prompt(
        "critique", brand_voice=ctx.brand_voice, custom=ctx.custom_prompt("critique")
    )
    user = (
        f"RESEARCH (ground claims against this):\n{json.dumps(research_data, indent=2)}\n\n"
        f"{SEO_CHECKLIST}\n\n"
        f"DRAFT TO EDIT AND AUDIT:\n{draft_markdown}"
    )
    try:
        parsed = await ctx.llm.complete_json(system, user)
    except (LlmUnavailable, Exception) as exc:  # noqa: BLE001
        logger.warning("Critique stage degraded: %s", exc)
        return {
            "edited_markdown": draft_markdown,
            "claims": [],
            "ai_tells_found": base_seo["ai_tells"],
            "fluff_removed": f"skipped ({exc})",
            "checklist": base_seo["checks"],
            "seo": base_seo,
            "degraded": True,
        }

    edited = parsed.get("edited_markdown") or draft_markdown if isinstance(parsed, dict) else draft_markdown
    # Re-score the edited version deterministically — that's the published baseline.
    final_seo = seo.evaluate(edited, keyword)
    result = parsed if isinstance(parsed, dict) else {}
    result["edited_markdown"] = edited
    result["seo"] = final_seo
    return result
