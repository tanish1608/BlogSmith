"""Domain enums and constants shared across the service.

The actual documents are stored as plain dicts in Firestore (Pydantic models in
``schemas.py`` validate the API boundary). This module holds the vocabulary —
run lifecycle states and the canonical stage names — so every layer agrees.
"""

from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    """The 9 pipeline stages. Each writes a same-named JSON slice on the run doc."""

    DISCOVERY = "discovery"
    RESEARCH = "research"
    OUTLINE = "outline"
    DRAFT = "draft"
    CRITIQUE = "critique"
    EXPERT = "expert"          # human email-gate decision + edits
    FINAL = "final"            # finalize output (title/meta/schema/links/placements)
    VISUALS = "visuals"        # generated images
    DISTRIBUTION = "distribution"  # LinkedIn thread


# Order in which stage slices appear in API responses / the dashboard.
STAGE_ORDER: list[str] = [s.value for s in Stage]


class RunStatus(StrEnum):
    """Lifecycle of a single blog run."""

    QUEUED = "queued"
    DISCOVERING = "discovering"
    RESEARCHING = "researching"
    OUTLINING = "outlining"
    DRAFTING = "drafting"
    CRITIQUING = "critiquing"
    AWAITING_EXPERT = "awaiting_expert"  # paused at the email gate
    FINALIZING = "finalizing"
    GENERATING_IMAGES = "generating_images"
    DISTRIBUTING = "distributing"
    DONE = "done"
    REJECTED = "rejected"
    CANCELLED = "cancelled"  # stopped by the user mid-run
    FAILED = "failed"


# Statuses from which a run is considered finished (no further processing).
TERMINAL_STATUSES = {
    RunStatus.DONE,
    RunStatus.REJECTED,
    RunStatus.CANCELLED,
    RunStatus.FAILED,
}


class ExpertDecision(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class DiscoverySource(StrEnum):
    SEED = "seed"          # manual seed topics + scraped Google autocomplete (free default)
    GSC = "gsc"            # Google Search Console (stub adapter)
    SERP = "serp"          # paid SERP provider for autocomplete + PAA (stub adapter)
