"""Pydantic v2 models for the API boundary — these drive the Swagger schema.

Naming mirrors the CleanCrawl convention: request models end in ``In``/``Create``,
responses end in ``Out``. Stage outputs are returned as free-form dicts (the
per-stage JSON slices) so the API returns what the graph wrote without transform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from blogsmith.models import DiscoverySource

# ── Account / provider keys (BYOK) ────────────────────────────────────────────


class ProviderKeysIn(BaseModel):
    """Keys a user pastes into their profile. All optional; only set ones update."""

    gemini_key: str | None = Field(default=None, description="Google Gemini API key (required to generate).")
    langsmith_key: str | None = Field(default=None, description="LangSmith key for tracing (optional).")
    serp_key: str | None = Field(default=None, description="SERP provider key for discovery (optional).")


class AccountOut(BaseModel):
    uid: str
    email: str | None = None
    plan: str = "free"
    # Masked hints only — never the real keys.
    keys: dict[str, str | None] = Field(default_factory=dict)


# ── Site configuration ────────────────────────────────────────────────────────


class CustomPrompts(BaseModel):
    """Per-stage prompt additions layered onto the authored defaults.

    Each field, when set, is appended to that stage's system prompt. Leave blank
    to use BlogSmith's default behaviour for that stage.
    """

    brand_voice: str | None = Field(default=None, description="Global voice/tone rules applied to every stage.")
    discovery: str | None = None
    research: str | None = None
    outline: str | None = None
    draft: str | None = None
    critique: str | None = None
    finalize: str | None = None
    visuals: str | None = None
    distribute: str | None = None


class InternalLink(BaseModel):
    title: str
    url: str
    keywords: list[str] = Field(default_factory=list, description="Anchor-intent keywords for matching.")


class DiscoveryConfig(BaseModel):
    source: DiscoverySource = DiscoverySource.SEED
    seed_topics: list[str] = Field(default_factory=list)
    gsc_site_url: str | None = None  # used by the (stubbed) GSC adapter
    serp_country: str = "us"


class ScheduleConfig(BaseModel):
    enabled: bool = False
    cadence: str = Field(default="daily", description="daily | weekly")
    times: list[str] = Field(default_factory=lambda: ["09:00"], description="HH:MM local times to fire.")
    timezone: str = Field(default="UTC", description="IANA tz, e.g. 'America/New_York'.")
    days_of_week: list[int] = Field(default_factory=list, description="0=Mon..6=Sun (weekly only; empty=all).")
    count_per_run: int = Field(default=1, ge=1, le=50, description="Blogs to enqueue each fire.")


class SiteIn(BaseModel):
    name: str
    domain: str
    brand_voice: str | None = None
    custom_prompts: CustomPrompts = Field(default_factory=CustomPrompts)
    image_style: str | None = Field(default=None, description="Visual style guidance for generated images.")
    pillar_cluster_map: dict[str, list[str]] = Field(default_factory=dict, description="pillar -> cluster keywords.")
    internal_links: list[InternalLink] = Field(default_factory=list)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    approval_email: str | None = Field(default=None, description="Where draft approval emails go (defaults to account email).")


class SiteUpdate(BaseModel):
    """Partial update — every field optional."""

    name: str | None = None
    domain: str | None = None
    brand_voice: str | None = None
    custom_prompts: CustomPrompts | None = None
    image_style: str | None = None
    pillar_cluster_map: dict[str, list[str]] | None = None
    internal_links: list[InternalLink] | None = None
    discovery: DiscoveryConfig | None = None
    schedule: ScheduleConfig | None = None
    approval_email: str | None = None


class SiteOut(SiteIn):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Runs ──────────────────────────────────────────────────────────────────────


class RunCreate(BaseModel):
    topic: str | None = Field(default=None, description="Skip Discovery and write this exact topic.")
    keyword: str | None = Field(default=None, description="Primary target keyword (optional).")
    notes: str | None = Field(default=None, description="Freeform guidance for this single post.")
    expert_insights: str | None = Field(
        default=None,
        description="Optional war story / real numbers / contrarian take to weave in (the E-E-A-T layer).",
    )
    auto_approve: bool = Field(default=False, description="Skip the email gate (testing / trusted automation).")


class RunDecision(BaseModel):
    """The human review decision, submitted from the dashboard at the gate."""

    decision: str = Field(description="approve | edit | reject")
    edits: str | None = Field(default=None, description="Edited markdown body (required for 'edit').")


class RunOut(BaseModel):
    id: str
    site_id: str
    status: str
    topic: str | None = None
    keyword: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Per-stage JSON slices (discovery, research, ... distribution).
    stages: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    """The publishable output, pulled from the run's `final`/`visuals`/`distribution` slices."""

    id: str
    site_id: str
    status: str
    title: str | None = None
    meta_description: str | None = None
    slug: str | None = None
    markdown: str | None = None
    json_ld: dict[str, Any] | None = None
    images: list[dict[str, Any]] = Field(default_factory=list)
    linkedin_thread: list[str] = Field(default_factory=list)
