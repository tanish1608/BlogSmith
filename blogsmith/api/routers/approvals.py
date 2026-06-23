"""Approvals router — the email-gate landing endpoints.

Public by design: these URLs are clicked from an email, so authorisation is the
signed JWT in the path, not a bearer token. Approve/edit resume the run in the
background (finalize → visuals → distribute); reject stops it.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Form
from fastapi.responses import HTMLResponse

from blogsmith.email_gate import verify_token
from blogsmith.firestore_db import run_doc
from blogsmith.models import ExpertDecision
from blogsmith.runner import execute_resume

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#0f172a}}
textarea{{width:100%;height:50vh;font-family:ui-monospace,monospace;font-size:14px;padding:12px;border:1px solid #cbd5e1;border-radius:8px}}
button{{background:#2563eb;color:#fff;border:0;padding:12px 20px;border-radius:8px;font-size:15px;cursor:pointer}}
</style></head><body><h2>{title}</h2>{body}</body></html>"""
    )


def _invalid() -> HTMLResponse:
    return _page("Link expired or invalid", "<p>This approval link is no longer valid. "
                 "Trigger a new run if you still need to publish this post.</p>")


@router.get("/{token}", response_class=HTMLResponse)
async def handle_link(token: str, background: BackgroundTasks) -> HTMLResponse:
    try:
        claims = verify_token(token)
    except Exception:  # noqa: BLE001 — expired/tampered token
        return _invalid()

    uid, site_id, run_id = claims["uid"], claims["site_id"], claims["run_id"]
    action = claims["action"]

    if action == ExpertDecision.APPROVE.value:
        background.add_task(execute_resume, uid, site_id, run_id, ExpertDecision.APPROVE.value, None)
        return _page("Approved ✓", "<p>Publishing now — finalizing metadata, generating images, "
                     "and creating your LinkedIn thread. Check the dashboard in a moment.</p>")

    if action == ExpertDecision.REJECT.value:
        await execute_resume(uid, site_id, run_id, ExpertDecision.REJECT.value, None)
        return _page("Rejected ✕", "<p>This draft was rejected and will not be published.</p>")

    if action == ExpertDecision.EDIT.value:
        snap = run_doc(uid, site_id, run_id).get()
        stages = (snap.to_dict() or {}).get("stages", {}) if snap.exists else {}
        current = (stages.get("critique") or {}).get("edited_markdown") or (
            stages.get("draft") or {}
        ).get("markdown", "")
        return _page(
            "Edit your draft",
            f"""<p>Make your changes — add the war story, the real number, the contrarian take —
            then publish.</p>
            <form method="post" action="/approvals/{token}">
              <textarea name="edited_markdown">{_escape(current)}</textarea>
              <p><button type="submit">Save &amp; publish</button></p>
            </form>""",
        )

    return _invalid()


@router.post("/{token}", response_class=HTMLResponse)
async def submit_edit(
    token: str, background: BackgroundTasks, edited_markdown: str = Form(...)
) -> HTMLResponse:
    try:
        claims = verify_token(token)
    except Exception:  # noqa: BLE001
        return _invalid()
    if claims["action"] != ExpertDecision.EDIT.value:
        return _invalid()

    background.add_task(
        execute_resume,
        claims["uid"], claims["site_id"], claims["run_id"],
        ExpertDecision.EDIT.value, edited_markdown,
    )
    return _page("Saved ✓", "<p>Your edits were saved and the post is publishing now. "
                 "Check the dashboard shortly.</p>")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
