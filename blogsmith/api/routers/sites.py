"""Sites router — one config per website/domain.

A site holds the brand voice, per-stage custom prompts, pillar/cluster map,
internal-link map, discovery config, and publishing schedule. Blogs (runs) are
created under a site and inherit all of it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from google.cloud import firestore

from blogsmith.accounts import ensure_user
from blogsmith.api.auth import AuthedUser, current_user
from blogsmith.csv_io import config_to_csv, parse_config_csv
from blogsmith.firestore_db import site_doc, sites_col
from blogsmith.schemas import SiteIn, SiteOut, SiteUpdate

router = APIRouter(prefix="/sites", tags=["sites"])


async def _read_csv(file: UploadFile) -> str:
    raw = await file.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be UTF-8 CSV text.") from None


def _to_site_out(doc_id: str, data: dict[str, Any]) -> SiteOut:
    return SiteOut(id=doc_id, **data)


def _load_or_404(uid: str, site_id: str):
    snap = site_doc(uid, site_id).get()
    if not snap.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found.")
    return snap


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteIn, user: AuthedUser = Depends(current_user)) -> SiteOut:
    ensure_user(user.uid, user.email)
    data = payload.model_dump()
    ref = sites_col(user.uid).document()
    ref.set({**data, "created_at": firestore.SERVER_TIMESTAMP, "updated_at": firestore.SERVER_TIMESTAMP})
    return _to_site_out(ref.id, ref.get().to_dict() or data)


@router.get("", response_model=list[SiteOut])
async def list_sites(user: AuthedUser = Depends(current_user)) -> list[SiteOut]:
    return [_to_site_out(d.id, d.to_dict() or {}) for d in sites_col(user.uid).stream()]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(site_id: str, user: AuthedUser = Depends(current_user)) -> SiteOut:
    snap = _load_or_404(user.uid, site_id)
    return _to_site_out(snap.id, snap.to_dict() or {})


@router.patch("/{site_id}", response_model=SiteOut)
async def update_site(
    site_id: str, payload: SiteUpdate, user: AuthedUser = Depends(current_user)
) -> SiteOut:
    _load_or_404(user.uid, site_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates:
        updates["updated_at"] = firestore.SERVER_TIMESTAMP
        site_doc(user.uid, site_id).update(updates)
    snap = site_doc(user.uid, site_id).get()
    return _to_site_out(snap.id, snap.to_dict() or {})


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_site(site_id: str, user: AuthedUser = Depends(current_user)) -> Response:
    _load_or_404(user.uid, site_id)
    site_doc(user.uid, site_id).delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Config as CSV (download current → edit → re-upload) ───────────────────────


@router.get("/{site_id}/config.csv")
async def download_config_csv(site_id: str, user: AuthedUser = Depends(current_user)) -> Response:
    """Download this site's current config as an editable CSV template."""
    snap = _load_or_404(user.uid, site_id)
    data = snap.to_dict() or {}
    csv_text = config_to_csv(data)
    slug = (data.get("domain") or data.get("name") or "site").replace("/", "-")
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{slug}-config.csv"'},
    )


@router.post("/{site_id}/config-csv", response_model=SiteOut)
async def upload_config_csv(
    site_id: str,
    file: UploadFile = File(...),
    user: AuthedUser = Depends(current_user),
) -> SiteOut:
    """Apply a config CSV. ``name`` and ``domain`` are locked and never changed."""
    snap = _load_or_404(user.uid, site_id)
    current = snap.to_dict() or {}
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
    updates["updated_at"] = firestore.SERVER_TIMESTAMP
    site_doc(user.uid, site_id).update(updates)
    snap = site_doc(user.uid, site_id).get()
    return _to_site_out(snap.id, snap.to_dict() or {})
