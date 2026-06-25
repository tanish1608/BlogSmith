"""Stage 8 — Visuals.

For each [[IMAGE: ...]] placeholder, generate the image with Gemini, upload it to
Firebase Storage, and replace the placeholder with a Markdown image. On failure,
diagrammable types degrade to an inline Mermaid block and photos are dropped — the
post is always left clean and complete.
"""

from __future__ import annotations

import asyncio
import logging

from blogsmith.graph.context import RunContext
from blogsmith.graph.image_model import mermaid_fallback
from blogsmith.markdown_utils import ImagePlaceholder, parse_image_placeholders, replace_placeholder
from blogsmith.storage import save_image

logger = logging.getLogger(__name__)


def _spec_for(images_spec: list[dict], index: int) -> dict:
    for s in images_spec:
        if s.get("placeholder_index") == index:
            return s
    return {}


async def _produce_one(
    ctx: RunContext, images_spec: list[dict], ph: ImagePlaceholder
) -> tuple[ImagePlaceholder, str, dict]:
    """Generate/replace a single placeholder. Returns (placeholder, replacement, record)."""
    spec = _spec_for(images_spec, ph.index)
    prompt = spec.get("generation_prompt") or ph.description
    alt = spec.get("alt_text") or ph.alt
    img_type = spec.get("type") or ph.type

    image = await ctx.images.generate(prompt, style=ctx.image_style)
    if image is not None:
        try:
            url = save_image(
                site_id=ctx.site_id,
                run_id=ctx.run_id,
                index=ph.index,
                data=image.data,
                content_type=image.mime_type,
            )
            record = {"index": ph.index, "type": img_type, "url": url, "alt": alt}
            return ph, f"![{alt}]({url})", record
        except Exception as exc:  # noqa: BLE001 — save failed, try fallback
            logger.warning("Image save failed for placeholder %s: %s", ph.index, exc)

    # Fallback path: Mermaid for diagrams, otherwise drop the placeholder.
    mermaid = await mermaid_fallback(ctx.llm, img_type, prompt)
    if mermaid:
        return ph, mermaid, {"index": ph.index, "type": img_type, "mermaid": True, "alt": alt}
    return ph, "", {"index": ph.index, "type": img_type, "skipped": True, "alt": alt}


async def generate_visuals(ctx: RunContext, markdown: str, images_spec: list[dict]) -> dict:
    placeholders = parse_image_placeholders(markdown)
    if not placeholders:
        return {"images": [], "markdown": markdown}

    # Generate every image concurrently — they're independent. (This was the
    # pipeline's biggest serial cost: N image calls back-to-back.)
    results = await asyncio.gather(
        *(_produce_one(ctx, images_spec, ph) for ph in placeholders)
    )

    out_md = markdown
    produced: list[dict] = []
    for ph, replacement, record in results:
        out_md = replace_placeholder(out_md, ph, replacement)
        produced.append(record)

    return {"images": produced, "markdown": out_md}
