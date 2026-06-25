"""Publish a finished post to the Field Notes API.

POSTs the full ``.mdx`` (frontmatter + body) to the configured endpoint with a
bearer token. Create and update are the same call — the post's ``slug`` is the id,
so re-publishing just overwrites. See ``docs/field-notes-api.md``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

from blogsmith.config import get_settings

logger = logging.getLogger(__name__)

# Image content types the assets endpoint accepts (SVG is rejected upstream).
_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


class PublishNotConfigured(RuntimeError):
    """Publishing is disabled or no token is set."""


class PublishError(RuntimeError):
    """The Field Notes API rejected the post or was unreachable."""

    def __init__(self, message: str, *, status: int | None = None, details: list[str] | None = None):
        super().__init__(message)
        self.status = status
        self.details = details or []


def _assets_url(publish_url: str) -> str:
    """Derive the asset endpoint from the publish endpoint (.../field-notes → .../field-notes/assets)."""
    return publish_url.rstrip("/") + "/assets"


def _local_media_path(media_url: str) -> Path | None:
    """Map a served media URL (/media/<rel>) back to its file on disk, or None."""
    settings = get_settings()
    prefix = settings.media_url_prefix.rstrip("/")
    if not media_url.startswith(prefix + "/"):
        return None
    rel = media_url[len(prefix) + 1:]
    path = Path(settings.images_dir) / rel
    return path if path.is_file() else None


async def upload_asset(
    data: bytes, filename: str, content_type: str, *, assets_url: str, token: str, slug: str | None = None
) -> str:
    """Upload one image to the Field Notes asset endpoint; return its absolute URL."""
    files = {"file": (filename, data, content_type)}
    form = {"slug": slug} if slug else None
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(assets_url, files=files, data=form, headers=headers)
    except httpx.HTTPError as exc:
        raise PublishError(f"Could not reach the asset endpoint: {exc}") from exc

    try:
        payload = res.json()
    except ValueError:
        payload = {}
    if res.is_success and payload.get("url"):
        return payload["url"]

    message = payload.get("error") or f"Asset upload failed ({res.status_code})."
    raise PublishError(message, status=res.status_code)


async def upload_assets_and_rewrite(mdx: str, *, base_url: str, token: str, slug: str | None = None) -> str:
    """Find every local /media image in the MDX, host it on the site's bucket, and
    swap the relative path for the returned absolute URL. Posts with no local images
    pass through unchanged."""
    prefix = re.escape(get_settings().media_url_prefix.rstrip("/"))
    pattern = re.compile(rf"{prefix}/[^\s)\"']+?\.(?:png|jpe?g|gif|webp|avif)", re.IGNORECASE)
    media_urls = list(dict.fromkeys(pattern.findall(mdx)))  # unique, order-preserving
    if not media_urls:
        return mdx

    assets_url = _assets_url(base_url)
    for media_url in media_urls:
        path = _local_media_path(media_url)
        if path is None:
            logger.warning("Skipping missing local image %s", media_url)
            continue
        ext = path.suffix.lower()
        content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")
        absolute = await upload_asset(
            path.read_bytes(), path.name, content_type, assets_url=assets_url, token=token, slug=slug
        )
        mdx = mdx.replace(media_url, absolute)
    return mdx


async def publish_mdx(mdx: str, *, url: str | None = None, token: str | None = None) -> dict:
    """Send one ``.mdx`` document to the Field Notes API.

    The caller resolves the target (per-site config, else the ``.env`` default)
    and passes ``token`` explicitly — there is deliberately no implicit token
    fallback, so a disabled target never publishes. ``url`` defaults to the
    configured endpoint. Returns the API payload (``{ok, slug, url, draft}``) on
    success. Raises :class:`PublishNotConfigured` if no token was given, or
    :class:`PublishError` (carrying the upstream status + ``details``) otherwise.
    """
    url = url or get_settings().field_notes_url
    if not token:
        raise PublishNotConfigured(
            "Publishing is not configured. Enable it for this site (with a token), "
            "or set PUBLISH_ENABLED=true and FIELD_NOTES_TOKEN in .env."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/markdown",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, content=mdx, headers=headers)
    except httpx.HTTPError as exc:
        raise PublishError(f"Could not reach the Field Notes API: {exc}") from exc

    try:
        data = res.json()
    except ValueError:
        data = {}

    if res.is_success:
        return data

    # Surface the upstream error + its `details` list (the API explains what to fix).
    message = data.get("error") or f"Publish failed ({res.status_code})."
    raise PublishError(message, status=res.status_code, details=data.get("details", []))
