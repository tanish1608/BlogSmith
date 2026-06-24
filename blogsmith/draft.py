"""Stage 4 — Draft.

The writer. Produces the first full Markdown draft in the site's brand voice,
following the outline, weaving in the human expert insight, and emitting
[[IMAGE: ...]] placeholders where the outline planned visuals.

Unlike the degradable stages, drafting REQUIRES a working model — a blog server
that silently emits an empty post is worse than one that fails loudly.
"""

from __future__ import annotations

import json
import logging

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.markdown_utils import ends_abruptly
from blogsmith.prompts import build_system_prompt

logger = logging.getLogger(__name__)


async def _ensure_closing(ctx: RunContext, system: str, markdown: str) -> str:
    """Repair a draft that stopped without a proper conclusion.

    The outline-following writer occasionally ends on a sub-heading or a partial
    numbered list (e.g. "Step 2"), leaving the post hanging. When we detect that,
    ask the model once for just the missing closing section and append it.
    """
    if not ends_abruptly(markdown):
        return markdown
    logger.info("Draft ended abruptly — requesting a closing section.")
    try:
        closing = await ctx.llm.complete(
            system,
            "The following article is missing its ending — it stops without a conclusion. "
            "Write ONLY the final closing section to append: a real H2 heading (not "
            '"Conclusion"/"Summary"), 1-2 short paragraphs delivering the key takeaway and one '
            "concrete next step. Do not repeat earlier content. Output only the new Markdown.\n\n"
            f"ARTICLE SO FAR:\n{markdown}",
        )
        closing = closing.strip()
        if closing:
            return f"{markdown.rstrip()}\n\n{closing}"
    except (LlmUnavailable, Exception) as exc:  # noqa: BLE001 — keep the draft we have
        logger.warning("Closing repair failed: %s", exc)
    return markdown


async def draft(ctx: RunContext, outline_data: dict, research_data: dict) -> dict:
    if not ctx.llm.available:
        raise LlmUnavailable(
            "Drafting requires a Gemini API key. Add one in your account settings."
        )

    system = build_system_prompt(
        "draft", brand_voice=ctx.brand_voice, custom=ctx.custom_prompt("draft")
    )
    user = (
        f"OUTLINE (follow this structure):\n{json.dumps(outline_data, indent=2)}\n\n"
        f"RESEARCH (use only these facts):\n{json.dumps(research_data, indent=2)}\n\n"
        f"EXPERT INSIGHT TO WEAVE IN (the E-E-A-T layer): "
        f"{ctx.expert_insights or 'none provided — write from the research only'}\n\n"
        f"Extra guidance for this post: {ctx.run_input.get('notes') or 'none'}\n\n"
        "Write the full article in Markdown now."
    )
    markdown = await ctx.llm.complete(system, user)
    markdown = await _ensure_closing(ctx, system, markdown.strip())
    return {"markdown": markdown.strip()}
