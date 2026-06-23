"""Account router — profile + BYOK provider keys.

Users are created on the Firebase dashboard; this endpoint lazily mirrors them
into Firestore on first call and lets them store their Gemini (and optional)
keys, which are encrypted at rest.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from blogsmith.accounts import ensure_user, masked_keys, set_keys
from blogsmith.api.auth import AuthedUser, current_user
from blogsmith.schemas import AccountOut, ProviderKeysIn

router = APIRouter(prefix="/account", tags=["account"])


@router.get("", response_model=AccountOut)
async def get_account(user: AuthedUser = Depends(current_user)) -> AccountOut:
    data = ensure_user(user.uid, user.email)
    return AccountOut(
        uid=user.uid,
        email=data.get("email"),
        plan=data.get("plan", "free"),
        keys=masked_keys(user.uid),
    )


@router.put("/keys", response_model=AccountOut)
async def update_keys(
    payload: ProviderKeysIn, user: AuthedUser = Depends(current_user)
) -> AccountOut:
    ensure_user(user.uid, user.email)
    set_keys(user.uid, payload.model_dump())
    data = ensure_user(user.uid, user.email)
    return AccountOut(
        uid=user.uid,
        email=data.get("email"),
        plan=data.get("plan", "free"),
        keys=masked_keys(user.uid),
    )
