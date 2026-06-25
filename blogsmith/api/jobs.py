"""Run dispatch — concurrent, in-process background execution.

A run's Phase A (discovery → review gate / completion) executes detached from the
request so the API stays responsive; Phase B is triggered later by a dashboard
review decision.

Runs are launched as **asyncio tasks on the event loop**, not FastAPI
``BackgroundTasks`` (those run sequentially after the response — so a CSV of N
topics would drain one-at-a-time). A semaphore caps how many run concurrently
(``max_concurrent_runs``) so we never stampede the Gemini rate limits. Each live
task is tracked by run id so the dashboard can cancel a run mid-flight.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import BackgroundTasks

from blogsmith import store
from blogsmith.config import get_settings
from blogsmith.models import TERMINAL_STATUSES, RunStatus
from blogsmith.runner import execute_run

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
# Live run tasks keyed by run id — strong refs (so they aren't GC'd) + cancel handles.
_run_tasks: dict[str, asyncio.Task] = {}


def _get_semaphore() -> asyncio.Semaphore:
    """Lazily create the semaphore bound to the running loop."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, get_settings().max_concurrent_runs))
    return _semaphore


def _mark_cancelled(site_id: str, run_id: str) -> None:
    """Stamp the run as cancelled unless it already reached a terminal state."""
    run = store.get_run(site_id, run_id)
    if run and run.get("status") in {s.value for s in TERMINAL_STATUSES}:
        return
    try:
        store.update_run(site_id, run_id, {"status": RunStatus.CANCELLED.value})
    except Exception:  # noqa: BLE001
        logger.exception("Failed to mark run %s cancelled", run_id)


async def _run_guarded(site_id: str, run_id: str) -> None:
    try:
        async with _get_semaphore():
            await execute_run(site_id, run_id)
    except asyncio.CancelledError:
        # Cancelled while queued or mid-stage → record it as the final write.
        _mark_cancelled(site_id, run_id)
        raise
    except Exception:  # noqa: BLE001 — failure is already recorded on the run row
        logger.exception("Run %s failed", run_id)


def dispatch_run(
    site_id: str, run_id: str, background: BackgroundTasks | None = None
) -> str:
    """Kick off Phase A concurrently on the event loop.

    ``background`` is accepted for call-site compatibility but intentionally
    unused — we schedule on the loop so multiple runs progress in parallel.
    """
    task = asyncio.create_task(_run_guarded(site_id, run_id))
    _run_tasks[run_id] = task
    task.add_done_callback(lambda _t, rid=run_id: _run_tasks.pop(rid, None))
    return "background"


def cancel_run(run_id: str) -> bool:
    """Cancel a live run task if one is in flight. Returns True if a task was cancelled."""
    task = _run_tasks.get(run_id)
    if task is not None and not task.done():
        task.cancel()
        return True
    return False
