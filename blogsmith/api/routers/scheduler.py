"""Scheduler router — the Cloud Scheduler tick.

One cron job calls ``POST /scheduler/tick`` (OIDC + a shared secret). The handler
scans every site, fires the due time-slots, and enqueues ``count_per_run`` blog
runs per slot — fanning out from a single cron instead of per-user jobs.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from google.cloud import firestore

from blogsmith import firestore_db
from blogsmith.api.jobs import dispatch_run
from blogsmith.config import get_settings
from blogsmith.schedule import slots_due

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/tick")
async def tick(
    background: BackgroundTasks,
    x_scheduler_secret: str | None = Header(default=None),
) -> dict:
    settings = get_settings()
    if x_scheduler_secret != settings.scheduler_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bad scheduler secret.")

    now = datetime.now(UTC)
    enqueued = 0
    fired_sites = 0

    for uid, site_id, data in firestore_db.all_sites():
        if not uid:
            continue
        schedule = data.get("schedule", {}) or {}
        state = dict(data.get("schedule_state", {}) or {})
        due = slots_due(schedule, now, state)
        if not due:
            continue

        count = int(schedule.get("count_per_run", 1) or 1)
        for slot in due:
            for _ in range(count):
                ref = firestore_db.runs_col(uid, site_id).document()
                ref.set(
                    {
                        "status": "queued",
                        "input": {"auto_approve": False, "scheduled": True, "slot": slot["time"]},
                        "topic": None,
                        "keyword": None,
                        "stages": {},
                        "created_at": firestore.SERVER_TIMESTAMP,
                        "updated_at": firestore.SERVER_TIMESTAMP,
                    }
                )
                dispatch_run(uid, site_id, ref.id, background)
                enqueued += 1
            state[slot["key"]] = slot["date"]

        firestore_db.site_doc(uid, site_id).update({"schedule_state": state})
        fired_sites += 1

    logger.info("Scheduler tick: %d runs enqueued across %d sites.", enqueued, fired_sites)
    return {"enqueued": enqueued, "sites_fired": fired_sites, "at": now.isoformat()}
