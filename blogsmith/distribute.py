"""Stage 9 — Distribute.

Repurposes the finished post into a LinkedIn thread (where B2B buyers are). The
thread is returned/stored only — v1 does not auto-post. ``{{POST_URL}}`` is left
as a placeholder for the user to fill when they publish.
"""

from __future__ import annotations

import logging

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.markdown_utils import strip_markdown
from blogsmith.prompts import build_system_prompt

logger = logging.getLogger(__name__)


def _fallback_thread(title: str, markdown: str) -> list[str]:
    text = strip_markdown(markdown)
    hook = f"{title}\n\nHere's the short version 👇"
    body = (text[:300] + "…") if len(text) > 300 else text
    return [hook, body, "Full post: {{POST_URL}}"]


async def distribute(ctx: RunContext, markdown: str, title: str) -> dict:
    if not ctx.llm.available:
        return {"linkedin_thread": _fallback_thread(title, markdown), "degraded": True}

    system = build_system_prompt(
        "distribute", brand_voice=ctx.brand_voice, custom=ctx.custom_prompt("distribute")
    )
    user = f"Article title: {title}\n\nARTICLE:\n{markdown}\n\nWrite the LinkedIn thread now."
    try:
        parsed = await ctx.llm.complete_json(system, user)
        thread = parsed.get("thread", []) if isinstance(parsed, dict) else []
        if thread:
            return {"linkedin_thread": thread}
    except (LlmUnavailable, Exception) as exc:  # noqa: BLE001
        logger.warning("Distribute stage degraded: %s", exc)
    return {"linkedin_thread": _fallback_thread(title, markdown), "degraded": True}
