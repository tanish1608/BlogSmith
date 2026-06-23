"""Stage 2 — Research.

Builds the evidence base for the post, biasing toward primary sources for
regulatory/legal/medical/financial topics and separating verified from unverified
claims. Model-driven in v1 (the prompt enforces source discipline); a real web /
SERP retrieval layer can be slotted in behind the same return shape later.
"""

from __future__ import annotations

import logging

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.prompts import build_system_prompt

logger = logging.getLogger(__name__)


def _empty(topic: str) -> dict:
    return {
        "summary": f"(no research available for {topic})",
        "key_facts": [],
        "primary_sources": [],
        "statistics": [],
        "angles_competitors_miss": [],
        "degraded": True,
    }


async def research(ctx: RunContext, topic: dict) -> dict:
    title = topic.get("title", "")
    keyword = topic.get("primary_keyword", title)
    if not ctx.llm.available:
        return _empty(title)

    system = build_system_prompt(
        "research", brand_voice=ctx.brand_voice, custom=ctx.custom_prompt("research")
    )
    user = (
        f"Topic: {title}\n"
        f"Primary keyword: {keyword}\n"
        f"Audience/domain: {ctx.site.get('domain')}\n"
        f"Notes: {ctx.run_input.get('notes') or 'none'}\n"
        "Gather the research base now."
    )
    try:
        parsed = await ctx.llm.complete_json(system, user)
        if isinstance(parsed, dict):
            return parsed
    except (LlmUnavailable, Exception) as exc:  # noqa: BLE001
        logger.warning("Research stage degraded: %s", exc)
    return _empty(title)
