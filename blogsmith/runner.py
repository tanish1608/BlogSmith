"""Run execution — assemble a RunContext from Firestore and drive the graph.

Shared by the dispatcher (Phase A, kicked off when a run is created or scheduled)
and the approvals router (Phase B, on email link click). Secrets are decrypted
here and live only on the in-memory context, never in the graph state/checkpoint.
"""

from __future__ import annotations

import logging

from blogsmith.accounts import get_user_keys
from blogsmith.firestore_db import run_doc, site_doc
from blogsmith.graph.blog_graph import resume_pipeline, run_pipeline
from blogsmith.graph.checkpoint import is_resumable, state_from_run
from blogsmith.graph.context import RunContext
from blogsmith.graph.image_model import ImageClient
from blogsmith.graph.model import LlmBudget, LlmClient
from blogsmith.models import ExpertDecision, RunStatus

logger = logging.getLogger(__name__)


class RunNotFound(RuntimeError):
    pass


def _build_context(uid: str, site_id: str, run_id: str) -> tuple[RunContext, dict]:
    site_snap = site_doc(uid, site_id).get()
    if not site_snap.exists:
        raise RunNotFound(f"Site {site_id} not found.")
    run_snap = run_doc(uid, site_id, run_id).get()
    if not run_snap.exists:
        raise RunNotFound(f"Run {run_id} not found.")

    site = site_snap.to_dict() or {}
    run_data = run_snap.to_dict() or {}
    keys = get_user_keys(uid)
    budget = LlmBudget()
    llm = LlmClient(keys.get("gemini_key"), budget)
    images = ImageClient(keys.get("gemini_key"))

    run_input = run_data.get("input", {}) or {}
    ctx = RunContext(
        uid=uid,
        site_id=site_id,
        run_id=run_id,
        site=site,
        run_input=run_input,
        llm=llm,
        images=images,
        auto_approve=bool(run_input.get("auto_approve")),
    )
    return ctx, run_data


def build_preview_context(
    uid: str, site_id: str | None = None, run_input: dict | None = None
) -> RunContext:
    """A non-persisting context for stage-test endpoints (/discover, /draft, /preview-image)."""
    site: dict = {}
    if site_id:
        snap = site_doc(uid, site_id).get()
        if not snap.exists:
            raise RunNotFound(f"Site {site_id} not found.")
        site = snap.to_dict() or {}
    keys = get_user_keys(uid)
    budget = LlmBudget()
    return RunContext(
        uid=uid,
        site_id=site_id or "preview",
        run_id="preview",
        site=site,
        run_input=run_input or {},
        llm=LlmClient(keys.get("gemini_key"), budget),
        images=ImageClient(keys.get("gemini_key")),
        persist_enabled=False,
    )


async def execute_run(uid: str, site_id: str, run_id: str) -> None:
    """Phase A: discovery → gate (pause) or → done (auto-approve)."""
    ctx, _ = _build_context(uid, site_id, run_id)
    await run_pipeline(ctx)


async def execute_resume(
    uid: str, site_id: str, run_id: str, decision: str, edits: str | None = None
) -> str:
    """Phase B: apply the expert decision. Returns the resulting status."""
    ctx, run_data = _build_context(uid, site_id, run_id)

    if decision == ExpertDecision.REJECT.value:
        ctx.set_status(RunStatus.REJECTED.value)
        ctx.persist("expert", {"decision": decision})
        return RunStatus.REJECTED.value

    if not is_resumable(run_data):
        raise RunNotFound("Run is not at a resumable stage.")

    state = state_from_run(run_data)
    result = await resume_pipeline(ctx, state, decision=decision, edits=edits)
    return result.get("status", RunStatus.DONE.value)
