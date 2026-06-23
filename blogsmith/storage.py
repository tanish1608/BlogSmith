"""Firebase Storage helpers for generated blog images.

The Visuals stage uploads each Gemini-generated image here and embeds the public
URL in the post markdown. Objects live at:
    {uid}/{site_id}/{run_id}/img-{n}.{ext}
"""

from __future__ import annotations

import logging

from firebase_admin import storage

from blogsmith.config import get_settings
from blogsmith.firestore_db import init_firebase

logger = logging.getLogger(__name__)


def upload_image(
    *,
    uid: str,
    site_id: str,
    run_id: str,
    index: int,
    data: bytes,
    content_type: str = "image/png",
) -> str:
    """Upload image bytes and return a publicly readable URL.

    Raises on failure — the Visuals stage decides whether to fall back to Mermaid.
    """
    init_firebase()
    settings = get_settings()
    ext = "png" if "png" in content_type else content_type.split("/")[-1]
    path = f"{uid}/{site_id}/{run_id}/img-{index}.{ext}"

    bucket = storage.bucket(settings.firebase_storage_bucket)
    blob = bucket.blob(path)
    blob.upload_from_string(data, content_type=content_type)

    try:
        blob.make_public()
        url = blob.public_url
    except Exception:  # noqa: BLE001 — emulator/uniform-access buckets reject ACLs
        # Fall back to the standard download URL shape (works on emulator too).
        url = (
            f"https://storage.googleapis.com/{settings.firebase_storage_bucket}/{path}"
        )
    logger.info("Uploaded image %s", path)
    return url
