"""Stage 7 — Finalize (stage 6 is the human review gate).

Produces publication metadata for the approved body without rewriting it:
title tag, meta description, slug, tags, content type, JSON-LD schema, and
per-placeholder image generation prompts + alt text. Author/publisher/dates in
the JSON-LD come from verified site config, never from the model. Deterministic
fallbacks keep this working without a model.
"""

from __future__ import annotations

import logging
from datetime import date

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.markdown_utils import first_h1, parse_image_placeholders, slugify, strip_markdown
from blogsmith.mdx import resolve_type
from blogsmith.prompts import build_system_prompt

logger = logging.getLogger(__name__)


def _authoritative_json_ld(json_ld: object, ctx: RunContext, title: str, keyword: str | None) -> dict:
    """Overwrite author/publisher/dates with verified site config, never guesses.

    The model tends to invent an author ("Enterprise AI Insights"), a fake logo
    URL, and a wrong publish date. We keep its headline/keywords and replace the
    identity + dates with real values from the site.
    """
    ld = dict(json_ld) if isinstance(json_ld, dict) else {}
    ld.setdefault("@context", "https://schema.org")
    ld.setdefault("@type", "BlogPosting")
    ld["headline"] = ld.get("headline") or title
    if keyword and not ld.get("keywords"):
        ld["keywords"] = keyword

    site = ctx.site or {}
    author = site.get("author") or {}
    org_name = author.get("name") or site.get("name") or site.get("domain") or "Editorial Team"
    domain = site.get("domain") or ""
    ld["author"] = {
        "@type": "Person" if author.get("name") else "Organization",
        "name": org_name,
    }
    publisher: dict = {"@type": "Organization", "name": site.get("name") or org_name}
    if domain:
        publisher["url"] = domain if domain.startswith("http") else f"https://{domain}"
    ld["publisher"] = publisher

    today = date.today().isoformat()
    ld["datePublished"] = today
    ld["dateModified"] = today
    return ld


def _fallback_tags(ctx: RunContext, keyword: str | None) -> list[str]:
    tags: list[str] = []
    if keyword:
        tags.append(keyword.lower())
    tags += [t.lower() for t in (ctx.site or {}).get("default_tags", [])]
    tags += [p.lower() for p in (ctx.site or {}).get("pillar_cluster_map", {})]
    seen: list[str] = []
    for t in tags:
        if t and t not in seen:
            seen.append(t)
    return seen[:6]


def _fallback_final(ctx: RunContext, markdown: str, topic_title: str, keyword: str | None) -> dict:
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
        "tags": _fallback_tags(ctx, keyword),
        "type": resolve_type(None, ctx.site),
        "json_ld": _authoritative_json_ld({}, ctx, title, keyword),
        "images": images,
        "degraded": True,
    }


async def finalize(ctx: RunContext, markdown: str, topic_title: str, keyword: str | None) -> dict:
    if not ctx.llm.available:
        return _fallback_final(ctx, markdown, topic_title, keyword)

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
            title = parsed["title"]
            parsed.setdefault("slug", slugify(title))
            parsed.setdefault("images", [])
            parsed["type"] = resolve_type(parsed.get("type"), ctx.site)
            if not parsed.get("tags"):
                parsed["tags"] = _fallback_tags(ctx, keyword)
            # Never trust model-authored identity/dates — stamp the real ones.
            parsed["json_ld"] = _authoritative_json_ld(
                parsed.get("json_ld"), ctx, title, keyword
            )
            return parsed
    except (LlmUnavailable, Exception) as exc:  # noqa: BLE001
        logger.warning("Finalize stage degraded: %s", exc)
    return _fallback_final(ctx, markdown, topic_title, keyword)
