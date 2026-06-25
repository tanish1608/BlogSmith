"""Account router — local key status.

Keys are read from ``.env`` (single local workspace), so this endpoint is
read-only: it reports which provider keys are configured (masked), letting the
dashboard show generation readiness.
"""

from __future__ import annotations

from fastapi import APIRouter

from blogsmith.accounts import masked_keys
from blogsmith.config import get_settings
from blogsmith.schemas import AccountOut

router = APIRouter(prefix="/account", tags=["account"])


@router.get("", response_model=AccountOut)
async def get_account() -> AccountOut:
    return AccountOut(
        uid="local",
        email=None,
        plan="local",
        keys=masked_keys(),
        publish_enabled=get_settings().publishing_ready,
    )
