"""Shared test fixtures.

Each test gets a fresh SQLite store in a temp file (no cloud, no auth, no Java).
"""

from __future__ import annotations

import os

import pytest

# Set before blogsmith.config builds Settings.
os.environ.setdefault("APP_ENV", "dev")


@pytest.fixture
def store_db(tmp_path, monkeypatch):
    """Point the SQLite store at a throwaway file for the duration of a test."""
    from blogsmith import store
    from blogsmith.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(settings, "images_dir", str(tmp_path / "media"))
    store.close()
    store.init_db()
    yield store
    store.close()


@pytest.fixture
def client(store_db):
    """A TestClient wired to the temp SQLite store.

    Entered as a context manager so the app runs the lifespan and keeps a single
    persistent event loop for the client's lifetime — matching real uvicorn, where
    dispatched runs (asyncio tasks) keep progressing across requests.
    """
    from fastapi.testclient import TestClient

    from blogsmith.api.main import create_app

    with TestClient(create_app()) as c:
        yield c


def wait_for_status(client, site_id: str, run_id: str, target: str, timeout: float = 10.0) -> str:
    """Poll a run until it reaches ``target`` (or any terminal status), giving the
    background asyncio task time to progress on the app's loop."""
    import time

    terminal = {"done", "failed", "rejected", target}
    deadline = time.monotonic() + timeout
    status = ""
    while time.monotonic() < deadline:
        status = client.get(f"/sites/{site_id}/runs/{run_id}").json()["status"]
        if status in terminal:
            return status
        time.sleep(0.05)
    return status


@pytest.fixture
def patched_runner(monkeypatch):
    """Swap the real Gemini clients for deterministic fakes during runs."""
    from tests.fakes import FakeImages, FakeLlm

    monkeypatch.setattr("blogsmith.runner.LlmClient", lambda *a, **k: FakeLlm())
    monkeypatch.setattr("blogsmith.runner.ImageClient", lambda *a, **k: FakeImages())
