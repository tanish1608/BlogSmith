"""Assemble the publishable ``.mdx`` file the target site consumes.

The downstream app expects MDX with YAML frontmatter and a body that may use a
small set of components (``<Callout>``, fenced code with ``title=``, etc.). This
module turns BlogSmith's finished pieces — the locked body, the finalize metadata
slice, and the site's verified author config — into that exact shape.

Frontmatter contract (mirrors the app's template):

    ---
    title: "..."
    description: "..."
    publishedAt: "YYYY-MM-DD"
    updatedAt: "YYYY-MM-DD"
    author:
      name: "..."
      role: "..."
      url: "..."
    tags: ["a", "b"]
    type: "guide"
    cinematic: false
    draft: false
    ---
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from blogsmith.markdown_utils import first_h1, slugify, strip_leading_h1

# Allowed values for the frontmatter ``type`` field; anything else falls back.
CONTENT_TYPES = (
    "guide",
    "teardown",
    "explainer",
    "comparison",
    "checklist",
    "opinion",
    "tutorial",
)
DEFAULT_TYPE = "guide"

DEFAULT_AUTHOR = {"name": "Editorial Team", "role": "Author", "url": "/about"}


def _yaml_str(value: str) -> str:
    """Double-quote a scalar, escaping for YAML."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _as_date(value: Any, fallback: date) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        # Accept ISO-ish strings; keep just the date part.
        return value.strip()[:10]
    return fallback.isoformat()


def _clean_tags(raw: Any, fallback: list[str]) -> list[str]:
    tags: list[str] = []
    source = raw if isinstance(raw, list) else fallback
    for t in source:
        if not isinstance(t, str):
            continue
        tag = t.strip().lower()
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:6]


def build_frontmatter(
    *,
    title: str,
    description: str,
    published_at: str,
    updated_at: str,
    author: dict[str, str],
    tags: list[str],
    content_type: str,
    draft: bool = False,
    cinematic: bool = False,
) -> str:
    a = {**DEFAULT_AUTHOR, **{k: v for k, v in (author or {}).items() if v}}
    tag_list = "[" + ", ".join(_yaml_str(t) for t in tags) + "]"
    lines = [
        "---",
        f"title: {_yaml_str(title)}",
        f"description: {_yaml_str(description)}",
        f"publishedAt: {_yaml_str(published_at)}",
        f"updatedAt: {_yaml_str(updated_at)}",
        "author:",
        f"  name: {_yaml_str(a['name'])}",
        f"  role: {_yaml_str(a['role'])}",
        f"  url: {_yaml_str(a['url'])}",
        f"tags: {tag_list}",
        f"type: {_yaml_str(content_type)}",
        f"cinematic: {'true' if cinematic else 'false'}",
        f"draft: {'true' if draft else 'false'}",
        "---",
    ]
    return "\n".join(lines)


def resolve_type(raw: Any, site: dict | None) -> str:
    candidate = (raw or (site or {}).get("content_type") or DEFAULT_TYPE)
    candidate = str(candidate).strip().lower()
    return candidate if candidate in CONTENT_TYPES else DEFAULT_TYPE


def to_mdx(
    body_markdown: str,
    final: dict[str, Any],
    site: dict[str, Any] | None = None,
    *,
    published_at: Any = None,
    updated_at: Any = None,
    keyword: str | None = None,
) -> str:
    """Return the full ``.mdx`` document (frontmatter + body).

    The leading H1 is lifted into the frontmatter ``title`` and removed from the
    body, matching the app's template (the renderer draws the title from
    frontmatter).
    """
    site = site or {}
    final = final or {}
    today = date.today()

    h1, body = strip_leading_h1(body_markdown or "")
    title = h1 or final.get("title") or first_h1(body_markdown or "") or "Untitled"

    description = final.get("meta_description") or ""

    fallback_tags: list[str] = []
    if keyword:
        fallback_tags.append(keyword)
    fallback_tags += list(site.get("default_tags") or [])
    fallback_tags += list((site.get("pillar_cluster_map") or {}).keys())

    fm = build_frontmatter(
        title=title,
        description=description,
        published_at=_as_date(published_at, today),
        updated_at=_as_date(updated_at, today),
        author=site.get("author") or {},
        tags=_clean_tags(final.get("tags"), fallback_tags),
        content_type=resolve_type(final.get("type"), site),
        draft=False,
    )
    return f"{fm}\n\n{body}\n"


def mdx_filename(final: dict[str, Any], body_markdown: str) -> str:
    slug = (final or {}).get("slug") or slugify(
        first_h1(body_markdown or "") or "post"
    )
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-") or "post"
    return f"{slug}.mdx"
