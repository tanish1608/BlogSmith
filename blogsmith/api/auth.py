"""Firebase Auth dependency.

Every protected endpoint depends on :func:`current_user`, which verifies the
Firebase ID token in the ``Authorization: Bearer <token>`` header and returns the
caller's uid + email. In dev, ``AUTH_DISABLED=true`` short-circuits to a fixed
dev identity so the dashboard and Swagger work without a real login.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as fb_auth

from blogsmith.config import get_settings
from blogsmith.firestore_db import init_firebase

logger = logging.getLogger(__name__)

# auto_error=False so we can return a clean 401 (and honour AUTH_DISABLED).
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthedUser:
    uid: str
    email: str | None


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthedUser:
    settings = get_settings()

    if settings.auth_disabled:
        return AuthedUser(uid=settings.dev_uid, email=settings.dev_email)

    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    init_firebase()
    try:
        decoded = fb_auth.verify_id_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001 — any verification error → 401
        logger.warning("ID token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthedUser(uid=decoded["uid"], email=decoded.get("email"))
