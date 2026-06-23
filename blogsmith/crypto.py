"""Symmetric encryption for BYOK provider keys stored in Firestore.

Users paste their Gemini / LangSmith / SendGrid / SERP keys into their profile;
we never store them in plaintext. Encryption uses Fernet (AES-128-CBC + HMAC).
In dev a throwaway key is generated at import time so nothing breaks without
configuration — but a stable ``KEY_ENCRYPTION_KEY`` must be set in prod or
encrypted values become unreadable across restarts.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from blogsmith.config import get_settings

logger = logging.getLogger(__name__)

_PREFIX = "enc::"  # marks a value as already-encrypted, so encrypt is idempotent


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.key_encryption_key
    if not key:
        if settings.is_prod:
            raise RuntimeError(
                "KEY_ENCRYPTION_KEY must be set in production to protect stored keys."
            )
        # Dev convenience: deterministic-per-process throwaway key.
        key = Fernet.generate_key().decode()
        logger.warning(
            "KEY_ENCRYPTION_KEY not set — using an ephemeral dev key. "
            "Stored secrets will not survive a restart."
        )
        settings.key_encryption_key = key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    """Encrypt a secret. Idempotent: already-encrypted values pass through."""
    if not value or value.startswith(_PREFIX):
        return value
    token = _fernet().encrypt(value.encode()).decode()
    return _PREFIX + token


def decrypt(value: str | None) -> str | None:
    """Decrypt a stored secret. Returns None for empty/undecryptable values."""
    if not value:
        return None
    if not value.startswith(_PREFIX):
        return value  # legacy/plaintext — return as-is
    try:
        return _fernet().decrypt(value[len(_PREFIX) :].encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt a stored secret (wrong KEY_ENCRYPTION_KEY?).")
        return None


def mask(value: str | None) -> str | None:
    """Return a display-safe hint of a secret, e.g. '••••abcd'. Never the real value."""
    if not value:
        return None
    plain = decrypt(value) or ""
    if len(plain) <= 4:
        return "••••"
    return "••••" + plain[-4:]
