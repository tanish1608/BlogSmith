"""Stage 3 — Outline.

Structures the post to match search intent and the site's pillar/cluster map,
planning internal links, visual placements, and where the human expert insight
should land. Falls back to a sensible default structure if the LLM is down.
"""

from __future__ import annotations

import logging

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.prompts import build_system_prompt

logger = logging.getLogger(__name__)


def _fallback_outline(topic: dict) -> dict:
    title = topic.get("title", "Untitled")
    kw = topic.get("primary_keyword", title)
    return {
        "h1": title,
        "target_keyword": kw,
        "search_intent": topic.get("search_intent", "informational"),
        "estimated_word_count": 1000,
        "sections": [
            {"heading": "Overview", "level": 2, "purpose": "answer the core question",
             "talking_points": [kw], "internal_link": None,
             "visual": {"type": "diagram", "shows": f"how {kw} works"},
             "expert_insight_slot": True, "children": []},
            {"heading": "Key considerations", "level": 2, "purpose": "depth",
             "talking_points": [], "internal_link": None, "visual": None,
             "expert_insight_slot": False, "children": []},
            {"heading": "Next steps", "level": 2, "purpose": "actionable close",
             "talking_points": [], "internal_link": None, "visual": None,
             "expert_insight_slot": False, "children": []},
        ],
        "degraded": True,
    }


async def outline(ctx: RunContext, topic: dict, research_data: dict) -> dict:
    if not ctx.llm.available:
        return _fallback_outline(topic)

    system = build_system_prompt(
        "outline", brand_voice=ctx.brand_voice, custom=ctx.custom_prompt("outline")
    )
    user = (
        f"Topic: {topic.get('title')}\n"
        f"Primary keyword: {topic.get('primary_keyword')}\n"
        f"Search intent: {topic.get('search_intent')}\n"
        f"Pillar/cluster map: {ctx.site.get('pillar_cluster_map', {})}\n"
        f"Internal links available: {ctx.site.get('internal_links', [])}\n"
        f"Research summary: {research_data.get('summary')}\n"
        f"Angles competitors miss: {research_data.get('angles_competitors_miss', [])}\n"
        f"Expert insight provided: {'yes' if ctx.expert_insights else 'no'}\n"
        "Build the outline now."
    )
    try:
        parsed = await ctx.llm.complete_json(system, user)
        if isinstance(parsed, dict) and parsed.get("sections"):
            return parsed
    except (LlmUnavailable, Exception) as exc:  # noqa: BLE001
        logger.warning("Outline stage degraded: %s", exc)
    return _fallback_outline(topic)
