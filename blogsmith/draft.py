"""Stage 4 — Draft.

The writer. Produces the first full Markdown draft in the site's brand voice,
following the outline, weaving in the human expert insight, and emitting
[[IMAGE: ...]] placeholders where the outline planned visuals.

Unlike the degradable stages, drafting REQUIRES a working model — a blog server
that silently emits an empty post is worse than one that fails loudly.
"""

from __future__ import annotations

import json

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.prompts import build_system_prompt


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
    return {"markdown": markdown.strip()}
