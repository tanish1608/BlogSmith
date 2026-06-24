"""Run dispatch — in-process background execution.

A run's Phase A (discovery → review gate / completion) executes detached from the
request so the API stays responsive; Phase B is triggered later by a dashboard
review decision. Fully local: runs execute as asyncio tasks in this process.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import BackgroundTasks

from blogsmith.runner import execute_run

logger = logging.getLogger(__name__)


def dispatch_run(site_id: str, run_id: str, background: BackgroundTasks | None) -> str:
    """Kick off Phase A in the background."""
    if background is not None:
        background.add_task(execute_run, site_id, run_id)
    else:
        # No request context (e.g. the scheduler) — fire-and-forget on the loop.
        asyncio.create_task(execute_run(site_id, run_id))
    return "background"
