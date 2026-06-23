"""Graph nodes — thin wrappers that run a stage, persist its slice, and advance
the run status. The stage logic itself lives in the top-level stage modules so it
stays unit-testable in isolation.
"""

from __future__ import annotations

import logging

from blogsmith import critique as critique_stage
from blogsmith import discovery as discovery_stage
from blogsmith import distribute as distribute_stage
from blogsmith import draft as draft_stage
from blogsmith import finalize as finalize_stage
from blogsmith import outline as outline_stage
from blogsmith import research as research_stage
from blogsmith import visuals as visuals_stage
from blogsmith.graph.context import ctx_from_config
from blogsmith.graph.state import BlogState
from blogsmith.models import ExpertDecision, RunStatus

logger = logging.getLogger(__name__)


def approved_markdown(state: BlogState) -> str:
    """The body to publish: expert edits > critique edit > raw draft."""
    expert = state.get("expert") or {}
    if expert.get("edits"):
        return expert["edits"]
    crit = state.get("critique") or {}
    if crit.get("edited_markdown"):
        return crit["edited_markdown"]
    return (state.get("draft") or {}).get("markdown", "")


def _selected_topic(state: BlogState) -> dict:
    disc = state.get("discovery") or {}
    if disc.get("selected"):
        return disc["selected"]
    topic = state.get("topic")
    return {"title": topic or "Untitled", "primary_keyword": state.get("keyword") or topic}


# ── Phase A nodes ─────────────────────────────────────────────────────────────


async def discovery_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    slice_ = await discovery_stage.discover(ctx)
    selected = slice_.get("selected") or {}
    ctx.persist("discovery", slice_, status=RunStatus.RESEARCHING)
    if selected:
        ctx.update_fields({"topic": selected.get("title"), "keyword": selected.get("primary_keyword")})
    return {
        "discovery": slice_,
        "topic": selected.get("title", state.get("topic")),
        "keyword": selected.get("primary_keyword", state.get("keyword")),
        "status": RunStatus.RESEARCHING.value,
    }


async def research_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    slice_ = await research_stage.research(ctx, _selected_topic(state))
    ctx.persist("research", slice_, status=RunStatus.OUTLINING)
    return {"research": slice_, "status": RunStatus.OUTLINING.value}


async def outline_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    slice_ = await outline_stage.outline(ctx, _selected_topic(state), state.get("research") or {})
    ctx.persist("outline", slice_, status=RunStatus.DRAFTING)
    return {"outline": slice_, "status": RunStatus.DRAFTING.value}


async def draft_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    slice_ = await draft_stage.draft(ctx, state.get("outline") or {}, state.get("research") or {})
    ctx.persist("draft", slice_, status=RunStatus.CRITIQUING)
    return {"draft": slice_, "status": RunStatus.CRITIQUING.value}


async def critique_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    keyword = _selected_topic(state).get("primary_keyword")
    slice_ = await critique_stage.critique(
        ctx, (state.get("draft") or {}).get("markdown", ""), state.get("research") or {}, keyword
    )
    ctx.persist("critique", slice_)
    return {"critique": slice_}


async def gate_node(state: BlogState, config: dict) -> dict:
    """The human email gate. Auto-approve continues; otherwise pause + email."""
    ctx = ctx_from_config(config)
    if ctx.auto_approve:
        expert = {"decision": ExpertDecision.APPROVE.value, "auto": True}
        ctx.persist("expert", expert, status=RunStatus.FINALIZING)
        return {"expert": expert, "status": RunStatus.FINALIZING.value}

    # Pause for the human expert. Email is sent best-effort (module added in task #6).
    try:
        from blogsmith.email_gate import send_draft_for_approval

        send_draft_for_approval(ctx, state)
    except Exception as exc:  # noqa: BLE001 — never lose the run because email failed
        logger.error("Failed to send approval email: %s", exc)
    expert = {"decision": "pending"}
    ctx.persist("expert", expert, status=RunStatus.AWAITING_EXPERT)
    return {"expert": expert, "status": RunStatus.AWAITING_EXPERT.value}


# ── Phase B nodes (after approval) ────────────────────────────────────────────


async def finalize_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    body = approved_markdown(state)
    topic = _selected_topic(state)
    slice_ = await finalize_stage.finalize(ctx, body, topic.get("title", ""), topic.get("primary_keyword"))
    slice_["body_markdown"] = body  # locked body carried to visuals
    ctx.persist("final", slice_, status=RunStatus.GENERATING_IMAGES)
    ctx.update_fields({"title": slice_.get("title"), "slug": slice_.get("slug")})
    return {"final": slice_, "status": RunStatus.GENERATING_IMAGES.value}


async def visuals_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    final = state.get("final") or {}
    slice_ = await visuals_stage.generate_visuals(
        ctx, final.get("body_markdown", ""), final.get("images", [])
    )
    ctx.persist("visuals", slice_, status=RunStatus.DISTRIBUTING)
    return {"visuals": slice_, "status": RunStatus.DISTRIBUTING.value}


async def distribute_node(state: BlogState, config: dict) -> dict:
    ctx = ctx_from_config(config)
    final = state.get("final") or {}
    body = (state.get("visuals") or {}).get("markdown") or final.get("body_markdown", "")
    slice_ = await distribute_stage.distribute(ctx, body, final.get("title", ""))
    ctx.persist("distribution", slice_, status=RunStatus.DONE)
    return {"distribution": slice_, "status": RunStatus.DONE.value}
