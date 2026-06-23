"""Run dispatch — Cloud Run Job in prod, in-process background task in dev.

Mirrors CleanCrawl's ``jobs.py`` toggle (``DISPATCH_TO_CLOUD_RUN``). A run's
Phase A (discovery → email gate / completion) executes detached from the request
so the API stays responsive; Phase B is triggered later by an approval link.
"""

from __future__ import annotations

import logging

from fastapi import BackgroundTasks

from blogsmith.config import get_settings
from blogsmith.runner import execute_run

logger = logging.getLogger(__name__)


def dispatch_run(uid: str, site_id: str, run_id: str, background: BackgroundTasks | None) -> str:
    """Kick off Phase A. Returns the dispatch mode used."""
    settings = get_settings()
    if settings.dispatch_to_cloud_run:
        _dispatch_cloud_run_job(uid, site_id, run_id)
        return "cloud_run"
    if background is not None:
        background.add_task(execute_run, uid, site_id, run_id)
        return "background"
    # No request context (e.g. scheduler tick) — fire-and-forget on the loop.
    import asyncio

    asyncio.create_task(execute_run(uid, site_id, run_id))
    return "background"


def _dispatch_cloud_run_job(uid: str, site_id: str, run_id: str) -> None:
    """Execute the Cloud Run Job with per-run env overrides."""
    from google.cloud import run_v2

    settings = get_settings()
    client = run_v2.JobsClient()
    name = (
        f"projects/{settings.firebase_project_id}/locations/"
        f"{settings.cloud_run_region}/jobs/{settings.cloud_run_job_name}"
    )
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                env=[
                    run_v2.EnvVar(name="RUN_UID", value=uid),
                    run_v2.EnvVar(name="RUN_SITE_ID", value=site_id),
                    run_v2.EnvVar(name="RUN_ID", value=run_id),
                ]
            )
        ]
    )
    client.run_job(request=run_v2.RunJobRequest(name=name, overrides=overrides))
    logger.info("Dispatched Cloud Run Job for run %s", run_id)
