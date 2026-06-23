"""Cadence logic — slots_due fires once per slot per day, catch-up safe."""

from __future__ import annotations

from datetime import UTC, datetime

from blogsmith.schedule import slots_due


def test_disabled_never_fires():
    assert slots_due({"enabled": False, "times": ["09:00"]}, datetime.now(UTC), {}) == []


def test_daily_slot_fires_after_its_time():
    now = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)  # 10:00 UTC
    sched = {"enabled": True, "cadence": "daily", "times": ["09:00"], "timezone": "UTC"}
    due = slots_due(sched, now, {})
    assert len(due) == 1
    assert due[0]["time"] == "09:00"
    assert due[0]["date"] == "2026-06-23"


def test_slot_does_not_refire_same_day():
    now = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    sched = {"enabled": True, "cadence": "daily", "times": ["09:00"], "timezone": "UTC"}
    state = {"daily:09:00": "2026-06-23"}
    assert slots_due(sched, now, state) == []


def test_slot_not_yet_due():
    now = datetime(2026, 6, 23, 8, 0, tzinfo=UTC)  # before 09:00
    sched = {"enabled": True, "cadence": "daily", "times": ["09:00"], "timezone": "UTC"}
    assert slots_due(sched, now, {}) == []


def test_timezone_respected():
    # 13:00 UTC == 09:00 America/New_York (EDT, UTC-4) in June.
    now = datetime(2026, 6, 23, 13, 30, tzinfo=UTC)
    sched = {"enabled": True, "cadence": "daily", "times": ["09:00"], "timezone": "America/New_York"}
    assert len(slots_due(sched, now, {})) == 1


def test_weekly_wrong_day_skipped():
    now = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)  # 2026-06-23 is a Tuesday (weekday 1)
    sched = {"enabled": True, "cadence": "weekly", "times": ["09:00"], "days_of_week": [0]}  # Monday only
    assert slots_due(sched, now, {}) == []
