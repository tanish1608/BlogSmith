"""The human-expert email gate.

When a run reaches the gate, the draft is emailed to the site's approval address
with three signed links — approve, edit, reject. Clicking a link hits the
approvals router, which verifies the token and resumes (or stops) the run. No
inbound mail parsing: the signed token carries everything needed to route the
reply back to the right run.
"""

from __future__ import annotations

import datetime as dt
import logging

import jwt

from blogsmith.config import get_settings
from blogsmith.graph.context import RunContext
from blogsmith.graph.state import BlogState
from blogsmith.models import ExpertDecision

logger = logging.getLogger(__name__)

_ALG = "HS256"


# ── Tokens ────────────────────────────────────────────────────────────────────


def sign_token(uid: str, site_id: str, run_id: str, action: str) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.UTC)
    payload = {
        "uid": uid,
        "site_id": site_id,
        "run_id": run_id,
        "action": action,
        "iat": now,
        "exp": now + dt.timedelta(hours=s.approval_token_ttl_hours),
    }
    return jwt.encode(payload, s.approval_token_secret, algorithm=_ALG)


def verify_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.approval_token_secret, algorithms=[_ALG])


def build_links(uid: str, site_id: str, run_id: str) -> dict[str, str]:
    base = get_settings().public_base_url.rstrip("/")
    out = {}
    for action in (ExpertDecision.APPROVE, ExpertDecision.EDIT, ExpertDecision.REJECT):
        token = sign_token(uid, site_id, run_id, action.value)
        out[action.value] = f"{base}/approvals/{token}"
    return out


# ── Sending ───────────────────────────────────────────────────────────────────


def _send_console(to: str, subject: str, html: str) -> None:
    logger.info("[email:console] To: %s | Subject: %s\n%s", to, subject, html)


def _send_sendgrid(to: str, subject: str, html: str, api_key: str) -> None:
    import httpx

    s = get_settings()
    resp = httpx.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": s.email_from, "name": s.email_from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        },
        timeout=10.0,
    )
    resp.raise_for_status()


def send_email(to: str, subject: str, html: str, *, sendgrid_key: str | None = None) -> None:
    s = get_settings()
    provider = s.email_provider
    key = sendgrid_key or s.sendgrid_api_key
    if provider == "sendgrid" and key:
        _send_sendgrid(to, subject, html, key)
    else:
        _send_console(to, subject, html)


# ── The gate email ────────────────────────────────────────────────────────────


def _recipient(ctx: RunContext) -> str:
    if ctx.site.get("approval_email"):
        return ctx.site["approval_email"]
    # Fall back to the account email.
    from blogsmith.firestore_db import user_doc

    try:
        data = user_doc(ctx.uid).get().to_dict() or {}
        if data.get("email"):
            return data["email"]
    except Exception:  # noqa: BLE001
        pass
    return get_settings().email_from


def _draft_for_review(state: BlogState) -> str:
    crit = state.get("critique") or {}
    return crit.get("edited_markdown") or (state.get("draft") or {}).get("markdown", "")


def render_email(ctx: RunContext, state: BlogState, links: dict[str, str]) -> str:
    topic = (state.get("discovery") or {}).get("selected") or {}
    title = topic.get("title") or state.get("topic") or "Your draft"
    body = _draft_for_review(state)
    return f"""\
<div style="font-family:system-ui,sans-serif;max-width:680px;margin:auto">
  <h2>Draft ready for your expert pass</h2>
  <p><strong>{title}</strong> for <em>{ctx.site.get('domain', '')}</em> is drafted and edited.
  Add your war story / real numbers / contrarian take, then choose an action:</p>
  <p>
    <a href="{links['approve']}" style="background:#16a34a;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;margin-right:8px">✓ Approve &amp; publish</a>
    <a href="{links['edit']}" style="background:#2563eb;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;margin-right:8px">✎ Edit</a>
    <a href="{links['reject']}" style="background:#dc2626;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none">✕ Reject</a>
  </p>
  <hr/>
  <pre style="white-space:pre-wrap;background:#f8fafc;padding:16px;border-radius:8px">{body}</pre>
</div>"""


def send_draft_for_approval(ctx: RunContext, state: BlogState) -> None:
    """Compose and send the gate email. Raises on send failure (caller logs)."""
    links = build_links(ctx.uid, ctx.site_id, ctx.run_id)
    html = render_email(ctx, state, links)
    to = _recipient(ctx)

    sendgrid_key = None
    try:
        from blogsmith.accounts import get_user_keys

        sendgrid_key = get_user_keys(ctx.uid).get("sendgrid_key")
    except Exception:  # noqa: BLE001
        pass

    subject = f"[BlogSmith] Draft ready: {state.get('topic') or ctx.site.get('domain', '')}"
    send_email(to, subject, html, sendgrid_key=sendgrid_key)
    logger.info("Sent approval email for run %s to %s", ctx.run_id, to)
