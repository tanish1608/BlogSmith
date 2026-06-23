"""Markdown helpers shared by the draft, finalize, and visuals stages.

Image placements use a portable placeholder the writer emits and the visuals
stage replaces:

    [[IMAGE: <type> | <what to show> | <draft alt text>]]
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PLACEHOLDER_RE = re.compile(r"\[\[IMAGE:\s*(.*?)\]\]", re.IGNORECASE)
_H1_RE = re.compile(r"^\s*#\s+(.*)$", re.MULTILINE)


@dataclass
class ImagePlaceholder:
    index: int
    type: str
    description: str
    alt: str
    raw: str  # the exact source text to replace


def parse_image_placeholders(markdown: str) -> list[ImagePlaceholder]:
    out: list[ImagePlaceholder] = []
    for i, match in enumerate(_PLACEHOLDER_RE.finditer(markdown)):
        body = match.group(1)
        parts = [p.strip() for p in body.split("|")]
        img_type = (parts[0] if parts else "diagram").lower() or "diagram"
        description = parts[1] if len(parts) > 1 else ""
        alt = parts[2] if len(parts) > 2 else description
        out.append(
            ImagePlaceholder(
                index=i, type=img_type, description=description, alt=alt, raw=match.group(0)
            )
        )
    return out


def replace_placeholder(markdown: str, placeholder: ImagePlaceholder, replacement: str) -> str:
    return markdown.replace(placeholder.raw, replacement, 1)


def first_h1(markdown: str) -> str | None:
    m = _H1_RE.search(markdown)
    return m.group(1).strip() if m else None


def strip_markdown(markdown: str) -> str:
    """Crude plain-text projection for keyword/first-100-word checks."""
    text = _PLACEHOLDER_RE.sub(" ", markdown)
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", text, flags=re.DOTALL)  # code
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)  # images
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)  # links → anchor text
    text = re.sub(r"[#>*_~\-]+", " ", text)  # md punctuation
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")
