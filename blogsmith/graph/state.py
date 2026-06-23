"""The channel-typed graph state.

Only data slices live here — never secrets. Provider keys and live clients are
passed at invoke time via the run context (see ``context.py``) so they are never
serialized into Firestore. Each stage writes its same-named slice; the slices are
exactly what the API returns.
"""

from __future__ import annotations

from typing import Any, TypedDict


class BlogState(TypedDict, total=False):
    # Inputs
    topic: str | None
    keyword: str | None

    # Per-stage outputs (mirror the run document's stage slices)
    discovery: dict[str, Any]
    research: dict[str, Any]
    outline: dict[str, Any]
    draft: dict[str, Any]        # {"markdown": "..."}
    critique: dict[str, Any]     # {"edited_markdown": "...", "claims": [...], ...}
    expert: dict[str, Any]       # {"decision": "approve|edit|reject", "edits": "..."}
    final: dict[str, Any]        # {"title", "meta_description", "slug", "json_ld", "images"}
    visuals: dict[str, Any]      # {"images": [{"url","alt","type"}], "markdown": "..."}
    distribution: dict[str, Any] # {"linkedin_thread": [...]}

    # Control
    status: str
    error: str | None
