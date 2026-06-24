"""Runs router — create a blog run under a site, check status, fetch the result.

Creating a run writes a ``queued`` document, dispatches Phase A (background task
in dev, Cloud Run Job in prod), and returns immediately. The pipeline updates the
document as it progresses, so polling ``GET`` shows live status.
"""

from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from google.cloud import firestore

from blogsmith.api.auth import AuthedUser, current_user
from blogsmith.api.jobs import dispatch_run
from blogsmith.csv_io import parse_runs_csv, runs_template_csv
from blogsmith.firestore_db import run_doc, runs_col, site_doc
from blogsmith.mdx import mdx_filename, to_mdx
from blogsmith.models import ExpertDecision, RunStatus
from blogsmith.runner import execute_resume
from blogsmith.schemas import RunCreate, RunDecision, RunOut, RunResult

router = APIRouter(prefix="/sites/{site_id}/runs", tags=["runs"])


def _require_site(uid: str, site_id: str) -> None:
    if not site_doc(uid, site_id).get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")


def _enqueue_run(
    uid: str, site_id: str, payload: RunCreate, background: BackgroundTasks
) -> RunOut:
    """Write a queued run document and dispatch Phase A."""
    ref = runs_col(uid, site_id).document()
    ref.set(
        {
            "status": "queued",
            "input": payload.model_dump(),
            "topic": payload.topic,
            "keyword": payload.keyword,
            "stages": {},
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )
    dispatch_run(uid, site_id, ref.id, background)
    return _run_out(site_id, ref.id, ref.get().to_dict() or {})


def _run_out(site_id: str, run_id: str, data: dict[str, Any]) -> RunOut:
    return RunOut(
        id=run_id,
        site_id=site_id,
        status=data.get("status", "unknown"),
        topic=data.get("topic"),
        keyword=data.get("keyword"),
        error=data.get("error"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        stages=data.get("stages", {}),
    )


@router.post("", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    site_id: str,
    payload: RunCreate,
    background: BackgroundTasks,
    user: AuthedUser = Depends(current_user),
) -> RunOut:
    _require_site(user.uid, site_id)
    return _enqueue_run(user.uid, site_id, payload, background)


@router.get("/template.csv")
async def download_runs_template(
    site_id: str, user: AuthedUser = Depends(current_user)
) -> Response:
    """Download the bulk-topics CSV template (topic, primary_keywords, expert_insights)."""
    _require_site(user.uid, site_id)
    return Response(
        content=runs_template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="blogs-template.csv"'},
    )


@router.post("/csv", response_model=list[RunOut], status_code=status.HTTP_202_ACCEPTED)
async def create_runs_csv(
    site_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    auto_approve: bool = False,
    user: AuthedUser = Depends(current_user),
) -> list[RunOut]:
    """Queue one blog run per row of an uploaded topics CSV."""
    _require_site(user.uid, site_id)
    try:
        text = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be UTF-8 CSV text.") from None

    rows = parse_runs_csv(text)
    if not rows:
        raise HTTPException(
            status_code=422,
            detail="No topics found. The CSV needs a 'topic' column with at least one row.",
        )

    created: list[RunOut] = []
    for row in rows:
        payload = RunCreate(**row, auto_approve=auto_approve)
        created.append(_enqueue_run(user.uid, site_id, payload, background))
    return created


@router.get("", response_model=list[RunOut])
async def list_runs(site_id: str, user: AuthedUser = Depends(current_user)) -> list[RunOut]:
    _require_site(user.uid, site_id)
    return [_run_out(site_id, d.id, d.to_dict() or {}) for d in runs_col(user.uid, site_id).stream()]


@router.get("/{run_id}", response_model=RunOut)
async def get_run(site_id: str, run_id: str, user: AuthedUser = Depends(current_user)) -> RunOut:
    snap = run_doc(user.uid, site_id, run_id).get()
    if not snap.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return _run_out(site_id, run_id, snap.to_dict() or {})


@router.post("/{run_id}/decision", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
async def submit_decision(
    site_id: str,
    run_id: str,
    payload: RunDecision,
    background: BackgroundTasks,
    user: AuthedUser = Depends(current_user),
) -> RunOut:
    """The human review gate, driven from the dashboard.

    approve → finalize → visuals → distribute; edit → same with the edited body;
    reject → stop. Runs in the background; poll GET to watch progress.
    """
    snap = run_doc(user.uid, site_id, run_id).get()
    if not snap.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    data = snap.to_dict() or {}
    if data.get("status") != RunStatus.AWAITING_EXPERT.value:
        raise HTTPException(status_code=409, detail="Run is not awaiting review.")

    valid = {d.value for d in ExpertDecision}
    if payload.decision not in valid:
        raise HTTPException(status_code=422, detail=f"decision must be one of {sorted(valid)}.")
    if payload.decision == ExpertDecision.EDIT.value and not payload.edits:
        raise HTTPException(status_code=422, detail="'edit' requires the edited markdown body.")

    background.add_task(
        execute_resume, user.uid, site_id, run_id, payload.decision, payload.edits
    )
    return _run_out(site_id, run_id, data)


@router.get("/{run_id}/result", response_model=RunResult)
async def get_result(site_id: str, run_id: str, user: AuthedUser = Depends(current_user)) -> RunResult:
    snap = run_doc(user.uid, site_id, run_id).get()
    if not snap.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    data = snap.to_dict() or {}
    stages = data.get("stages", {})
    final = stages.get("final", {}) or {}
    visuals = stages.get("visuals", {}) or {}
    distribution = stages.get("distribution", {}) or {}

    body = visuals.get("markdown") or final.get("body_markdown")
    site_snap = site_doc(user.uid, site_id).get()
    site = site_snap.to_dict() if site_snap.exists else {}

    mdx_doc = filename = None
    if body:
        mdx_doc = to_mdx(
            body,
            final,
            site,
            published_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            keyword=data.get("keyword"),
        )
        filename = mdx_filename(final, body)

    return RunResult(
        id=run_id,
        site_id=site_id,
        status=data.get("status", "unknown"),
        title=final.get("title"),
        meta_description=final.get("meta_description"),
        slug=final.get("slug"),
        markdown=body,
        mdx=mdx_doc,
        mdx_filename=filename,
        tags=final.get("tags", []),
        content_type=final.get("type"),
        json_ld=final.get("json_ld"),
        images=visuals.get("images", []),
        linkedin_thread=distribution.get("linkedin_thread", []),
    )
