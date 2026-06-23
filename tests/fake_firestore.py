"""A minimal in-memory Firestore stand-in for tests.

Implements just the slice of the google-cloud-firestore API that BlogSmith uses:
``collection`` / ``document`` (auto-id) / ``get`` / ``set`` / ``update`` (with
dotted field paths) / ``delete`` / ``stream`` / nested sub-collections, plus the
``SERVER_TIMESTAMP`` sentinel and snapshot ``.exists`` / ``.to_dict()`` / ``.id``.

This keeps the test suite JVM-free (the real Firestore emulator needs Java 21).
Point ``blogsmith.firestore_db.db`` at a :class:`FakeClient` to use it.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore as real_fs


def _now() -> datetime:
    return datetime.now(UTC)


def _resolve(value: Any) -> Any:
    """Replace SERVER_TIMESTAMP sentinels with a concrete time, recursively."""
    if value is real_fs.SERVER_TIMESTAMP:
        return _now()
    if isinstance(value, dict):
        return {k: _resolve(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v) for v in value]
    return value


def _set_dotted(target: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


class _Store:
    def __init__(self) -> None:
        self.docs: dict[str, _DocData] = {}


class _DocData:
    def __init__(self) -> None:
        self.data: dict | None = None
        self.subs: dict[str, _Store] = {}


class Snapshot:
    def __init__(self, doc_id: str, data: dict | None) -> None:
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict | None:
        return copy.deepcopy(self._data) if self._data is not None else None


class DocRef:
    def __init__(self, store: _Store, doc_id: str) -> None:
        self._store = store
        self.id = doc_id

    @property
    def _dd(self) -> _DocData:
        return self._store.docs.setdefault(self.id, _DocData())

    def get(self) -> Snapshot:
        return Snapshot(self.id, self._dd.data)

    def set(self, data: dict, merge: bool = False) -> None:
        resolved = _resolve(copy.deepcopy(data))
        if merge and self._dd.data:
            self._dd.data.update(resolved)
        else:
            self._dd.data = resolved

    def update(self, data: dict) -> None:
        if self._dd.data is None:
            self._dd.data = {}
        for key, value in data.items():
            value = _resolve(value)
            if "." in key:
                _set_dotted(self._dd.data, key, value)
            else:
                self._dd.data[key] = value

    def delete(self) -> None:
        self._dd.data = None
        self._dd.subs = {}

    def collection(self, name: str) -> CollectionRef:
        return CollectionRef(self._dd.subs.setdefault(name, _Store()))


class CollectionRef:
    def __init__(self, store: _Store) -> None:
        self._store = store

    def document(self, doc_id: str | None = None) -> DocRef:
        if doc_id is None:
            doc_id = uuid.uuid4().hex
        return DocRef(self._store, doc_id)

    def stream(self):
        for doc_id, dd in list(self._store.docs.items()):
            if dd.data is not None:
                yield Snapshot(doc_id, dd.data)


class FakeClient:
    def __init__(self) -> None:
        self._root: dict[str, _Store] = {}

    def collection(self, name: str) -> CollectionRef:
        return CollectionRef(self._root.setdefault(name, _Store()))
