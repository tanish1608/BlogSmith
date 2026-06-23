"""Runs router — create a blog run under a site, check status, fetch the result.

Creating a run writes a ``queued`` document, dispatches Phase A (background task
in dev, Cloud Run Job in prod), and returns immediately. The pipeline updates the
document as it progresses, so polling ``GET`` shows live status.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from google.cloud import firestore

from blogsmith.api.auth import AuthedUser, current_user
from blogsmith.api.jobs import dispatch_run
from blogsmith.firestore_db import run_doc, runs_col, site_doc
from blogsmith.schemas import RunCreate, RunOut, RunResult

router = APIRouter(prefix="/sites/{site_id}/runs", tags=["runs"])


def _require_site(uid: str, site_id: str) -> None:
    if not site_doc(uid, site_id).get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")


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
    ref = runs_col(user.uid, site_id).document()
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
    dispatch_run(user.uid, site_id, ref.id, background)
    return _run_out(site_id, ref.id, ref.get().to_dict() or {})


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
    return RunResult(
        id=run_id,
        site_id=site_id,
        status=data.get("status", "unknown"),
        title=final.get("title"),
        meta_description=final.get("meta_description"),
        slug=final.get("slug"),
        markdown=visuals.get("markdown") or final.get("body_markdown"),
        json_ld=final.get("json_ld"),
        images=visuals.get("images", []),
        linkedin_thread=distribution.get("linkedin_thread", []),
    )
