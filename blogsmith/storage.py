"""Local image storage for generated blog images.

The Visuals stage saves each Gemini-generated image to a local folder and embeds
a relative URL in the post markdown. Files live at:
    {images_dir}/{site_id}/{run_id}/img-{n}.{ext}
and are served by FastAPI under ``{media_url_prefix}`` (default ``/media``).
"""

from __future__ import annotations

import logging
from pathlib import Path

from blogsmith.config import get_settings

logger = logging.getLogger(__name__)


def save_image(
    *,
    site_id: str,
    run_id: str,
    index: int,
    data: bytes,
    content_type: str = "image/png",
) -> str:
    """Write image bytes to the local media folder and return its served URL.

    Raises on failure — the Visuals stage decides whether to fall back to Mermaid.
    """
    settings = get_settings()
    ext = "png" if "png" in content_type else content_type.split("/")[-1]
    rel = f"{site_id}/{run_id}/img-{index}.{ext}"

    dest = Path(settings.images_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    logger.info("Saved image %s", dest)
    return f"{settings.media_url_prefix.rstrip('/')}/{rel}"
