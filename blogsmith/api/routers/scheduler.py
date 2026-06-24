"""Scheduler router — manual tick.

The cadence scheduler runs automatically in-process (see
``blogsmith.scheduler_local``). This endpoint lets you fire a tick on demand from
the dashboard or Swagger.
"""

from __future__ import annotations

from fastapi import APIRouter

from blogsmith.scheduler_local import run_tick

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/tick")
async def tick() -> dict:
    return run_tick()
