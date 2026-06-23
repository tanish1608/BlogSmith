"""Stage 7 — Finalize (stage 6 is the human email gate).

Produces publication metadata for the approved body without rewriting it:
title tag, meta description, slug, JSON-LD schema, and per-placeholder image
generation prompts + alt text. Deterministic fallbacks keep this working without
a model.
"""

from __future__ import annotations

import logging

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.markdown_utils import first_h1, parse_image_placeholders, slugify, strip_markdown
from blogsmith.prompts import build_system_prompt

logger = logging.getLogger(__name__)


def _fallback_final(markdown: str, topic_title: str, keyword: str | None) -> dict:
    title = first_h1(markdown) or topic_title
    text = strip_markdown(markdown)
    meta = (text[:152] + "…") if len(text) > 153 else text
    images = [
        {
            "placeholder_index": ph.index,
            "type": ph.type,
            "generation_prompt": ph.description,
            "alt_text": ph.alt,
        }
        for ph in parse_image_placeholders(markdown)
    ]
    return {
        "title": title[:60],
        "meta_description": meta,
        "slug": slugify(title),
        "json_ld": {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title,
            "keywords": keyword or "",
        },
        "images": images,
        "degraded": True,
    }


async def finalize(ctx: RunContext, markdown: str, topic_title: str, keyword: str | None) -> dict:
    if not ctx.llm.available:
        return _fallback_final(markdown, topic_title, keyword)

    placeholders = parse_image_placeholders(markdown)
    system = build_system_prompt(
        "finalize", brand_voice=ctx.brand_voice, custom=ctx.custom_prompt("finalize")
    )
    user = (
        f"Primary keyword: {keyword}\n"
        f"Image placeholders in the body (index | type | description | alt):\n"
        + "\n".join(f"{p.index} | {p.type} | {p.description} | {p.alt}" for p in placeholders)
        + f"\n\nARTICLE (do not rewrite, just produce metadata):\n{markdown}"
    )
    try:
        parsed = await ctx.llm.complete_json(system, user)
        if isinstance(parsed, dict) and parsed.get("title"):
            parsed.setdefault("slug", slugify(parsed["title"]))
            parsed.setdefault("images", [])
            return parsed
    except (LlmUnavailable, Exception) as exc:  # noqa: BLE001
        logger.warning("Finalize stage degraded: %s", exc)
    return _fallback_final(markdown, topic_title, keyword)
