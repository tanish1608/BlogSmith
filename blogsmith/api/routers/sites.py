"""Sites router — one config per website/domain.

A site holds the brand voice, per-stage custom prompts, pillar/cluster map,
internal-link map, discovery config, author, and publishing schedule. Blogs
(runs) are created under a site and inherit all of it. Single local workspace,
no auth.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from blogsmith import store
from blogsmith.csv_io import config_to_csv, parse_config_csv
from blogsmith.schemas import SiteIn, SiteOut, SiteUpdate

router = APIRouter(prefix="/sites", tags=["sites"])


async def _read_csv(file: UploadFile) -> str:
    raw = await file.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be UTF-8 CSV text.") from None


_MASK = "••••"


def _mask_publish(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with the publish token masked — never ship the raw token."""
    pub = dict(data.get("publish") or {})
    token = pub.get("api_token")
    if token:
        pub["api_token"] = _MASK + str(token)[-4:] if len(str(token)) > 4 else _MASK
    out = dict(data)
    out["publish"] = pub
    return out


def _to_site_out(data: dict[str, Any]) -> SiteOut:
    return SiteOut(**_mask_publish(data))


def _preserve_publish_token(site_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """If an update carries a blank or masked publish token, keep the stored one."""
    pub = updates.get("publish")
    if not isinstance(pub, dict):
        return updates
    token = pub.get("api_token")
    if not token or str(token).startswith(_MASK):
        current = (store.get_site(site_id) or {}).get("publish") or {}
        pub["api_token"] = current.get("api_token")
    return updates


def _load_or_404(site_id: str) -> dict[str, Any]:
    site = store.get_site(site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    return site


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteIn) -> SiteOut:
    return _to_site_out(store.create_site(payload.model_dump()))


@router.get("", response_model=list[SiteOut])
async def list_sites() -> list[SiteOut]:
    return [_to_site_out(s) for s in store.list_sites()]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(site_id: str) -> SiteOut:
    return _to_site_out(_load_or_404(site_id))


@router.patch("/{site_id}", response_model=SiteOut)
async def update_site(site_id: str, payload: SiteUpdate) -> SiteOut:
    _load_or_404(site_id)
    updates = _preserve_publish_token(site_id, payload.model_dump(exclude_unset=True))
    site = store.update_site(site_id, updates) if updates else store.get_site(site_id)
    return _to_site_out(site)  # type: ignore[arg-type]


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_site(site_id: str) -> Response:
    _load_or_404(site_id)
    store.delete_site(site_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Config as CSV (download current → edit → re-upload) ───────────────────────


@router.get("/{site_id}/config.csv")
async def download_config_csv(site_id: str) -> Response:
    """Download this site's current config as an editable CSV template."""
    data = _load_or_404(site_id)
    csv_text = config_to_csv(data)
    slug = (data.get("domain") or data.get("name") or "site").replace("/", "-")
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{slug}-config.csv"'},
    )


@router.post("/{site_id}/config-csv", response_model=SiteOut)
async def upload_config_csv(site_id: str, file: UploadFile = File(...)) -> SiteOut:
    """Apply a config CSV. ``name`` and ``domain`` are locked and never changed."""
    current = _load_or_404(site_id)
    parsed = parse_config_csv(await _read_csv(file))
    if not parsed:
        raise HTTPException(status_code=422, detail="No recognizable config fields in the CSV.")

    # Shallow-merge nested objects onto current config so a partial sheet never
    # wipes sibling fields (e.g. updating author.name keeps author.url).
    merged: dict[str, Any] = {}
    for key, value in parsed.items():
        if isinstance(value, dict) and isinstance(current.get(key), dict):
            merged[key] = {**current[key], **value}
        else:
            merged[key] = value

    updates = SiteUpdate(**merged).model_dump(exclude_unset=True)
    return _to_site_out(store.update_site(site_id, updates))  # type: ignore[arg-type]
