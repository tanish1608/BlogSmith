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
    """A TestClient wired to the temp SQLite store."""
    from fastapi.testclient import TestClient

    from blogsmith.api.main import create_app

    return TestClient(create_app())


@pytest.fixture
def patched_runner(monkeypatch):
    """Swap the real Gemini clients for deterministic fakes during runs."""
    from tests.fakes import FakeImages, FakeLlm

    monkeypatch.setattr("blogsmith.runner.LlmClient", lambda *a, **k: FakeLlm())
    monkeypatch.setattr("blogsmith.runner.ImageClient", lambda *a, **k: FakeImages())
