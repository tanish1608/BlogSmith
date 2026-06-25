"""Run dispatch — concurrent, in-process background execution.

A run's Phase A (discovery → review gate / completion) executes detached from the
request so the API stays responsive; Phase B is triggered later by a dashboard
review decision.

Runs are launched as **asyncio tasks on the event loop**, not FastAPI
``BackgroundTasks`` (those run sequentially after the response — so a CSV of N
topics would drain one-at-a-time). A semaphore caps how many run concurrently
(``max_concurrent_runs``) so we never stampede the Gemini rate limits.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import BackgroundTasks

from blogsmith.config import get_settings
from blogsmith.runner import execute_run

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
# Hold strong references so in-flight tasks aren't garbage-collected mid-run.
_tasks: set[asyncio.Task] = set()


def _get_semaphore() -> asyncio.Semaphore:
    """Lazily create the semaphore bound to the running loop."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, get_settings().max_concurrent_runs))
    return _semaphore


async def _run_guarded(site_id: str, run_id: str) -> None:
    async with _get_semaphore():
        try:
            await execute_run(site_id, run_id)
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
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return "background"
