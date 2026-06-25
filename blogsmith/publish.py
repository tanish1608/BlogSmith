"""Publish a finished post to the Field Notes API.

POSTs the full ``.mdx`` (frontmatter + body) to the configured endpoint with a
bearer token. Create and update are the same call — the post's ``slug`` is the id,
so re-publishing just overwrites. See ``docs/field-notes-api.md``.
"""

from __future__ import annotations

import logging

import httpx

from blogsmith.config import get_settings

logger = logging.getLogger(__name__)


class PublishNotConfigured(RuntimeError):
    """Publishing is disabled or no token is set."""


class PublishError(RuntimeError):
    """The Field Notes API rejected the post or was unreachable."""

    def __init__(self, message: str, *, status: int | None = None, details: list[str] | None = None):
        super().__init__(message)
        self.status = status
        self.details = details or []


async def publish_mdx(mdx: str) -> dict:
    """Send one ``.mdx`` document to the Field Notes API.

    Returns the API payload (``{ok, slug, url, draft}``) on success. Raises
    :class:`PublishNotConfigured` if publishing isn't set up, or
    :class:`PublishError` (carrying the upstream status + ``details``) otherwise.
    """
    settings = get_settings()
    if not settings.publishing_ready:
        raise PublishNotConfigured(
            "Publishing is off. Set PUBLISH_ENABLED=true and FIELD_NOTES_TOKEN in .env."
        )

    headers = {
        "Authorization": f"Bearer {settings.field_notes_token}",
        "Content-Type": "text/markdown",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(settings.field_notes_url, content=mdx, headers=headers)
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
