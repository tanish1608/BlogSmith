"""Shared test fixtures.

- Forces dev auth + a stable encryption key + console email before any app import.
- Swaps Firestore for the in-memory :class:`FakeClient` so no JVM/emulator is needed.
"""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

# Must be set before blogsmith.config builds Settings.
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("KEY_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("EMAIL_PROVIDER", "console")


@pytest.fixture
def fake_db(monkeypatch):
    """Patch the Firestore client with a fresh in-memory fake for each test."""
    from tests.fake_firestore import FakeClient

    client = FakeClient()
    monkeypatch.setattr("blogsmith.firestore_db.db", lambda: client)
    monkeypatch.setattr("blogsmith.firestore_db.init_firebase", lambda: None)
    return client


@pytest.fixture
def client(fake_db):
    """A TestClient wired to the fake Firestore."""
    from fastapi.testclient import TestClient

    from blogsmith.api.main import create_app

    return TestClient(create_app())
