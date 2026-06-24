"""Local SQLite persistence — the single common database.

Replaces Firestore. Two tables, each row holding a JSON document plus id and
timestamps:

    sites(id, data, created_at, updated_at)
    runs (id, site_id, data, created_at, updated_at)

There is no per-user namespace — one shared local workspace. Documents are
returned as plain dicts (with ``id``/``created_at``/``updated_at`` overlaid), so
the API/runner code works with the same dict shapes the Firestore layer used.

``patch`` dicts accept one level of dotted keys (e.g. ``"stages.draft"``) so the
graph can persist a single stage slice without rewriting the whole document.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from blogsmith.config import get_settings

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_RESERVED = ("id", "site_id", "created_at", "updated_at")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _gen_id() -> str:
    return uuid.uuid4().hex[:20]


def _connect() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            path = get_settings().db_path
            _conn = sqlite3.connect(path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sites (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, site_id TEXT NOT NULL, data TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_site ON runs(site_id);
                """
            )
            _conn.commit()
        return _conn


def init_db() -> None:
    """Create the database/tables if needed (called on app startup)."""
    _connect()


def close() -> None:
    """Drop the cached connection (used by tests to repoint at a fresh DB)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def _payload(data: dict[str, Any]) -> str:
    """Serialize a document, dropping reserved/overlaid columns."""
    return json.dumps({k: v for k, v in data.items() if k not in _RESERVED})


def _apply_patch(doc: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if "." in key:
            top, sub = key.split(".", 1)
            nested = doc.get(top)
            if not isinstance(nested, dict):
                nested = {}
            nested[sub] = value
            doc[top] = nested
        else:
            doc[key] = value
    return doc


# ── Sites ─────────────────────────────────────────────────────────────────────


def _site_row(row: sqlite3.Row) -> dict[str, Any]:
    doc = json.loads(row["data"])
    doc.update(id=row["id"], created_at=row["created_at"], updated_at=row["updated_at"])
    return doc


def create_site(data: dict[str, Any]) -> dict[str, Any]:
    sid, now = _gen_id(), _now()
    with _lock:
        c = _connect()
        c.execute(
            "INSERT INTO sites(id, data, created_at, updated_at) VALUES(?,?,?,?)",
            (sid, _payload(data), now, now),
        )
        c.commit()
    return get_site(sid)  # type: ignore[return-value]


def get_site(site_id: str) -> dict[str, Any] | None:
    row = _connect().execute("SELECT * FROM sites WHERE id=?", (site_id,)).fetchone()
    return _site_row(row) if row else None


def list_sites() -> list[dict[str, Any]]:
    rows = _connect().execute("SELECT * FROM sites ORDER BY created_at").fetchall()
    return [_site_row(r) for r in rows]


def update_site(site_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        c = _connect()
        row = c.execute("SELECT data FROM sites WHERE id=?", (site_id,)).fetchone()
        if not row:
            return None
        doc = _apply_patch(json.loads(row["data"]), patch)
        c.execute(
            "UPDATE sites SET data=?, updated_at=? WHERE id=?",
            (_payload(doc), _now(), site_id),
        )
        c.commit()
    return get_site(site_id)


def delete_site(site_id: str) -> bool:
    with _lock:
        c = _connect()
        cur = c.execute("DELETE FROM sites WHERE id=?", (site_id,))
        c.execute("DELETE FROM runs WHERE site_id=?", (site_id,))
        c.commit()
        return cur.rowcount > 0


def site_exists(site_id: str) -> bool:
    return _connect().execute("SELECT 1 FROM sites WHERE id=?", (site_id,)).fetchone() is not None


# ── Runs ──────────────────────────────────────────────────────────────────────


def _run_row(row: sqlite3.Row) -> dict[str, Any]:
    doc = json.loads(row["data"])
    doc.update(
        id=row["id"], site_id=row["site_id"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
    return doc


def create_run(site_id: str, data: dict[str, Any]) -> dict[str, Any]:
    rid, now = _gen_id(), _now()
    with _lock:
        c = _connect()
        c.execute(
            "INSERT INTO runs(id, site_id, data, created_at, updated_at) VALUES(?,?,?,?,?)",
            (rid, site_id, _payload(data), now, now),
        )
        c.commit()
    return get_run(site_id, rid)  # type: ignore[return-value]


def get_run(site_id: str, run_id: str) -> dict[str, Any] | None:
    row = _connect().execute(
        "SELECT * FROM runs WHERE id=? AND site_id=?", (run_id, site_id)
    ).fetchone()
    return _run_row(row) if row else None


def list_runs(site_id: str) -> list[dict[str, Any]]:
    rows = _connect().execute(
        "SELECT * FROM runs WHERE site_id=? ORDER BY created_at DESC", (site_id,)
    ).fetchall()
    return [_run_row(r) for r in rows]


def update_run(site_id: str, run_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        c = _connect()
        row = c.execute(
            "SELECT data FROM runs WHERE id=? AND site_id=?", (run_id, site_id)
        ).fetchone()
        if not row:
            return None
        doc = _apply_patch(json.loads(row["data"]), patch)
        c.execute(
            "UPDATE runs SET data=?, updated_at=? WHERE id=?",
            (_payload(doc), _now(), run_id),
        )
        c.commit()
    return get_run(site_id, run_id)


def all_runs() -> list[dict[str, Any]]:
    rows = _connect().execute("SELECT * FROM runs").fetchall()
    return [_run_row(r) for r in rows]
