"""Runs router — create a blog run under a site, check status, fetch the result.

Creating a run writes a ``queued`` row, dispatches Phase A (in-process background
task), and returns immediately. The pipeline updates the row as it progresses, so
polling ``GET`` shows live status. Single local workspace, no auth.
"""

from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)

from blogsmith import store
from blogsmith.api.jobs import dispatch_run
from blogsmith.csv_io import parse_runs_csv, runs_template_csv
from blogsmith.mdx import mdx_filename, to_mdx
from blogsmith.models import ExpertDecision, RunStatus
from blogsmith.runner import execute_resume
from blogsmith.schemas import RunCreate, RunDecision, RunOut, RunResult

router = APIRouter(prefix="/sites/{site_id}/runs", tags=["runs"])


def _require_site(site_id: str) -> None:
    if not store.site_exists(site_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")


def _run_out(data: dict[str, Any]) -> RunOut:
    return RunOut(
        id=data["id"],
        site_id=data.get("site_id", ""),
        status=data.get("status", "unknown"),
        topic=data.get("topic"),
        keyword=data.get("keyword"),
        error=data.get("error"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        stages=data.get("stages", {}),
    )


def _enqueue_run(site_id: str, payload: RunCreate, background: BackgroundTasks) -> RunOut:
    """Write a queued run row and dispatch Phase A."""
    run = store.create_run(
        site_id,
        {
            "status": "queued",
            "input": payload.model_dump(),
            "topic": payload.topic,
            "keyword": payload.keyword,
            "stages": {},
        },
    )
    dispatch_run(site_id, run["id"], background)
    return _run_out(run)


@router.post("", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    site_id: str, payload: RunCreate, background: BackgroundTasks
) -> RunOut:
    _require_site(site_id)
    return _enqueue_run(site_id, payload, background)


@router.get("/template.csv")
async def download_runs_template(site_id: str) -> Response:
    """Download the bulk-topics CSV template (topic, primary_keywords, expert_insights)."""
    _require_site(site_id)
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
) -> list[RunOut]:
    """Queue one blog run per row of an uploaded topics CSV."""
    _require_site(site_id)
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

    return [_enqueue_run(site_id, RunCreate(**row, auto_approve=auto_approve), background) for row in rows]


@router.get("", response_model=list[RunOut])
async def list_runs(site_id: str) -> list[RunOut]:
    _require_site(site_id)
    return [_run_out(r) for r in store.list_runs(site_id)]


@router.get("/{run_id}", response_model=RunOut)
async def get_run(site_id: str, run_id: str) -> RunOut:
    run = store.get_run(site_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return _run_out(run)


@router.post("/{run_id}/decision", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
async def submit_decision(
    site_id: str, run_id: str, payload: RunDecision, background: BackgroundTasks
) -> RunOut:
    """The human review gate, driven from the dashboard.

    approve → finalize → visuals → distribute; edit → same with the edited body;
    reject → stop. Runs in the background; poll GET to watch progress.
    """
    run = store.get_run(site_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    if run.get("status") != RunStatus.AWAITING_EXPERT.value:
        raise HTTPException(status_code=409, detail="Run is not awaiting review.")

    valid = {d.value for d in ExpertDecision}
    if payload.decision not in valid:
        raise HTTPException(status_code=422, detail=f"decision must be one of {sorted(valid)}.")
    if payload.decision == ExpertDecision.EDIT.value and not payload.edits:
        raise HTTPException(status_code=422, detail="'edit' requires the edited markdown body.")

    background.add_task(execute_resume, site_id, run_id, payload.decision, payload.edits)
    return _run_out(run)


@router.get("/{run_id}/result", response_model=RunResult)
async def get_result(site_id: str, run_id: str) -> RunResult:
    run = store.get_run(site_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    stages = run.get("stages", {})
    final = stages.get("final", {}) or {}
    visuals = stages.get("visuals", {}) or {}
    distribution = stages.get("distribution", {}) or {}

    body = visuals.get("markdown") or final.get("body_markdown")
    site = store.get_site(site_id) or {}

    mdx_doc = filename = None
    if body:
        mdx_doc = to_mdx(
            body,
            final,
            site,
            published_at=run.get("created_at"),
            updated_at=run.get("updated_at"),
            keyword=run.get("keyword"),
        )
        filename = mdx_filename(final, body)

    return RunResult(
        id=run_id,
        site_id=site_id,
        status=run.get("status", "unknown"),
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
