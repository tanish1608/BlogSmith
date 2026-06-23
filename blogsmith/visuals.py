"""Stage 8 — Visuals.

For each [[IMAGE: ...]] placeholder, generate the image with Gemini, upload it to
Firebase Storage, and replace the placeholder with a Markdown image. On failure,
diagrammable types degrade to an inline Mermaid block and photos are dropped — the
post is always left clean and complete.
"""

from __future__ import annotations

import logging

from blogsmith.graph.context import RunContext
from blogsmith.graph.image_model import mermaid_fallback
from blogsmith.markdown_utils import parse_image_placeholders, replace_placeholder
from blogsmith.storage import upload_image

logger = logging.getLogger(__name__)


def _spec_for(images_spec: list[dict], index: int) -> dict:
    for s in images_spec:
        if s.get("placeholder_index") == index:
            return s
    return {}


async def generate_visuals(ctx: RunContext, markdown: str, images_spec: list[dict]) -> dict:
    placeholders = parse_image_placeholders(markdown)
    produced: list[dict] = []
    out_md = markdown

    for ph in placeholders:
        spec = _spec_for(images_spec, ph.index)
        prompt = spec.get("generation_prompt") or ph.description
        alt = spec.get("alt_text") or ph.alt
        img_type = spec.get("type") or ph.type

        image = await ctx.images.generate(prompt, style=ctx.image_style)
        if image is not None:
            try:
                url = upload_image(
                    uid=ctx.uid,
                    site_id=ctx.site_id,
                    run_id=ctx.run_id,
                    index=ph.index,
                    data=image.data,
                    content_type=image.mime_type,
                )
                out_md = replace_placeholder(out_md, ph, f"![{alt}]({url})")
                produced.append({"index": ph.index, "type": img_type, "url": url, "alt": alt})
                continue
            except Exception as exc:  # noqa: BLE001 — upload failed, try fallback
                logger.warning("Image upload failed for placeholder %s: %s", ph.index, exc)

        # Fallback path: Mermaid for diagrams, otherwise drop the placeholder.
        mermaid = await mermaid_fallback(ctx.llm, img_type, prompt)
        if mermaid:
            out_md = replace_placeholder(out_md, ph, mermaid)
            produced.append({"index": ph.index, "type": img_type, "mermaid": True, "alt": alt})
        else:
            out_md = replace_placeholder(out_md, ph, "")
            produced.append({"index": ph.index, "type": img_type, "skipped": True, "alt": alt})

    return {"images": produced, "markdown": out_md}
