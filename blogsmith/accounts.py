"""User-profile data access — BYOK key storage (encrypted) and retrieval.

The run executor calls :func:`get_user_keys` to obtain the *decrypted* Gemini
(and optional) keys for the caller; everything stored in Firestore is encrypted
via :mod:`blogsmith.crypto`.
"""

from __future__ import annotations

from google.cloud import firestore

from blogsmith.config import get_settings
from blogsmith.crypto import decrypt, encrypt, mask
from blogsmith.firestore_db import user_doc

# Provider keys we know how to store, in a stable order.
KEY_FIELDS = ("gemini_key", "langsmith_key", "serp_key", "sendgrid_key")


def ensure_user(uid: str, email: str | None) -> dict:
    """Create the user doc on first sight; keep email fresh. Returns the doc data."""
    ref = user_doc(uid)
    snap = ref.get()
    if not snap.exists:
        data = {
            "email": email,
            "plan": "free",
            "keys": {},
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        ref.set(data)
        return {**data, "keys": {}}
    data = snap.to_dict() or {}
    if email and data.get("email") != email:
        ref.update({"email": email, "updated_at": firestore.SERVER_TIMESTAMP})
        data["email"] = email
    return data


def set_keys(uid: str, keys: dict[str, str | None]) -> None:
    """Encrypt and persist any provided keys (None/blank values are ignored)."""
    updates: dict[str, str] = {}
    for field in KEY_FIELDS:
        value = keys.get(field)
        if value:
            updates[f"keys.{field}"] = encrypt(value)
    if updates:
        updates["updated_at"] = firestore.SERVER_TIMESTAMP
        user_doc(uid).update(updates)


def masked_keys(uid: str) -> dict[str, str | None]:
    """Display-safe map of which keys are set (masked hints, never plaintext)."""
    snap = user_doc(uid).get()
    stored = (snap.to_dict() or {}).get("keys", {}) if snap.exists else {}
    return {field: mask(stored.get(field)) for field in KEY_FIELDS}


def get_user_keys(uid: str) -> dict[str, str | None]:
    """Decrypted keys for run execution. Gemini falls back to the global dev key."""
    snap = user_doc(uid).get()
    stored = (snap.to_dict() or {}).get("keys", {}) if snap.exists else {}
    out = {field: decrypt(stored.get(field)) for field in KEY_FIELDS}
    if not out.get("gemini_key"):
        out["gemini_key"] = get_settings().fallback_gemini_key
    return out
