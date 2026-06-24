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


def strip_leading_h1(markdown: str) -> tuple[str | None, str]:
    """Split out the leading H1 (carried into MDX frontmatter as the title).

    Returns ``(title, body)`` where ``body`` is the article with the first H1
    line removed. If there is no leading H1, ``title`` is None and the body is
    returned unchanged.
    """
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = _H1_RE.match(line)
        if m:
            rest = lines[i + 1 :]
            # drop a single blank line immediately after the H1
            while rest and not rest[0].strip():
                rest.pop(0)
            return m.group(1).strip(), "\n".join(rest).strip()
        break  # first non-blank line isn't an H1 → nothing to strip
    return None, markdown.strip()


_HEADING_RE = re.compile(r"^\s{0,3}#{2,6}\s+\S", re.MULTILINE)


def ends_abruptly(markdown: str) -> bool:
    """Heuristic: does the article stop without a real closing?

    True when the last non-empty line is a heading (the writer dropped the
    section body), or when the final block of prose sits under an H3/deeper
    sub-heading — the classic "ends on Step 2 of a list" failure where no
    conclusion/takeaway/CTA was written.
    """
    text = markdown.strip()
    if not text:
        return True
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return True
    # Last non-empty line is itself a heading → section has no body.
    if re.match(r"^\s{0,3}#{1,6}\s+", lines[-1]):
        return True
    # Find the last heading and its level; if the tail lives under an H3+ it is
    # a sub-section, not a conclusion.
    last_level = 0
    for ln in lines:
        m = re.match(r"^\s{0,3}(#{1,6})\s+", ln)
        if m:
            last_level = len(m.group(1))
    return last_level >= 3


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
