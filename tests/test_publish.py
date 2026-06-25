"""Asset hosting: local /media images are uploaded and the MDX is rewritten to
absolute URLs before publishing."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from blogsmith import publish
from blogsmith.config import get_settings


class _Resp:
    is_success = True
    status_code = 201

    def json(self):
        return {"ok": True, "url": "https://bucket.example/field-notes/s/abc123.jpeg"}


class _Client:
    calls: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, files=None, data=None, headers=None):
        _Client.calls.append({"url": url, "files": files, "data": data, "headers": headers})
        return _Resp()


@pytest.mark.asyncio
async def test_uploads_media_and_rewrites(store_db):
    settings = get_settings()
    # A real local image where the served URL maps to it.
    img = Path(settings.images_dir) / "site1" / "run1" / "img-0.jpeg"
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")

    mdx = "---\ntitle: x\n---\n\n![A diagram](/media/site1/run1/img-0.jpeg)\n"
    _Client.calls.clear()
    with mock.patch.object(publish.httpx, "AsyncClient", _Client):
        out = await publish.upload_assets_and_rewrite(
            mdx, base_url="https://t.example/api/field-notes", token="tok", slug="s"
        )

    assert "/media/site1/run1/img-0.jpeg" not in out
    assert "https://bucket.example/field-notes/s/abc123.jpeg" in out
    assert len(_Client.calls) == 1
    assert _Client.calls[0]["url"] == "https://t.example/api/field-notes/assets"
    assert _Client.calls[0]["headers"]["Authorization"] == "Bearer tok"
    assert _Client.calls[0]["data"] == {"slug": "s"}


@pytest.mark.asyncio
async def test_no_images_is_passthrough(store_db):
    mdx = "---\ntitle: x\n---\n\nNo images here.\n"
    _Client.calls.clear()
    with mock.patch.object(publish.httpx, "AsyncClient", _Client):
        out = await publish.upload_assets_and_rewrite(
            mdx, base_url="https://t.example/api/field-notes", token="tok"
        )
    assert out == mdx
    assert _Client.calls == []
