"""In-process cadence scheduler.

Replaces Cloud Scheduler. A background loop ticks every
``scheduler_interval_seconds`` while the app runs: it scans every site, fires the
due time-slots, and enqueues ``count_per_run`` runs per slot. Per-slot "last
fired" state lives on the site row, so each slot fires once per day regardless of
tick frequency (catch-up safe, no double-fires).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from blogsmith import store
from blogsmith.api.jobs import dispatch_run
from blogsmith.config import get_settings
from blogsmith.schedule import slots_due

logger = logging.getLogger(__name__)


def run_tick() -> dict:
    """Fire all due slots across every site once. Returns a small summary."""
    now = datetime.now(UTC)
    enqueued = 0
    fired_sites = 0

    for site in store.list_sites():
        site_id = site["id"]
        schedule = site.get("schedule", {}) or {}
        state = dict(site.get("schedule_state", {}) or {})
        due = slots_due(schedule, now, state)
        if not due:
            continue

        count = int(schedule.get("count_per_run", 1) or 1)
        for slot in due:
            for _ in range(count):
                run = store.create_run(
                    site_id,
                    {
                        "status": "queued",
                        "input": {"auto_approve": False, "scheduled": True, "slot": slot["time"]},
                        "topic": None,
                        "keyword": None,
                        "stages": {},
                    },
                )
                dispatch_run(site_id, run["id"], None)
                enqueued += 1
            state[slot["key"]] = slot["date"]

        store.update_site(site_id, {"schedule_state": state})
        fired_sites += 1

    if enqueued:
        logger.info("Scheduler tick: %d runs enqueued across %d sites.", enqueued, fired_sites)
    return {"enqueued": enqueued, "sites_fired": fired_sites, "at": now.isoformat()}


async def scheduler_loop() -> None:
    """Tick forever at the configured interval (started in the app lifespan)."""
    interval = max(5, get_settings().scheduler_interval_seconds)
    logger.info("Local scheduler started (every %ds).", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            run_tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            logger.error("Scheduler tick failed: %s", exc)
