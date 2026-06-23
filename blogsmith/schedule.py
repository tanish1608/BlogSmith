"""Cadence logic for scheduled blogging.

A single Cloud Scheduler cron hits ``POST /scheduler/tick`` periodically; this
module decides which time-slots are due for a site at that moment. State is the
per-slot "last fired" date stored on the site, so each slot fires once per day
regardless of how often the tick runs (catch-up safe, no double-fires).
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def _parse_hhmm(value: str) -> tuple[int, int]:
    hh, mm = value.split(":")
    return int(hh), int(mm)


def slots_due(schedule: dict, now_utc: datetime, state: dict) -> list[dict]:
    """Return [{time, key, date}] for slots that should fire at ``now_utc``."""
    if not schedule.get("enabled"):
        return []

    try:
        tz = ZoneInfo(schedule.get("timezone", "UTC"))
    except Exception:  # noqa: BLE001 — bad tz string → UTC
        tz = ZoneInfo("UTC")
    local = now_utc.astimezone(tz)

    cadence = schedule.get("cadence", "daily")
    if cadence == "weekly":
        days = schedule.get("days_of_week") or []
        if days and local.weekday() not in days:
            return []

    today = local.date().isoformat()
    due: list[dict] = []
    for t in schedule.get("times") or ["09:00"]:
        try:
            hh, mm = _parse_hhmm(t)
        except Exception:  # noqa: BLE001 — skip malformed slot
            continue
        slot_dt = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if local < slot_dt:
            continue  # not time yet today
        key = f"{cadence}:{t}"
        if state.get(key) == today:
            continue  # already fired this slot today
        due.append({"time": t, "key": key, "date": today})
    return due
