"""Tools router — health + stage-test endpoints.

The stage-test endpoints let a user exercise individual pipeline stages from
Swagger or the dashboard without launching a full run — the CleanCrawl ``/extract``
/ ``/classify-url`` idea applied to discovery, drafting, and image generation.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from blogsmith import __version__
from blogsmith.api.auth import AuthedUser, current_user
from blogsmith.config import get_settings
from blogsmith.graph.model import LlmUnavailable

router = APIRouter(tags=["tools"])


@router.get("/health")
async def health() -> dict:
    """Liveness + which service-level integrations are configured."""
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "env": s.app_env,
        "integrations": {
            "firestore_emulator": bool(s.firestore_emulator_host),
            "auth_disabled": s.auth_disabled,
            "langsmith": bool(s.langsmith_api_key),
            "dispatch": "cloud_run" if s.dispatch_to_cloud_run else "in_process",
            "text_model": s.text_model,
            "image_model": s.image_model,
        },
    }


# ── Stage-test endpoints ──────────────────────────────────────────────────────


class DiscoverRequest(BaseModel):
    site_id: str


@router.post("/tools/discover", tags=["tools"])
async def discover(req: DiscoverRequest, user: AuthedUser = Depends(current_user)) -> dict:
    from blogsmith.discovery import discover as run_discover
    from blogsmith.runner import RunNotFound, build_preview_context

    try:
        ctx = build_preview_context(user.uid, req.site_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await run_discover(ctx)


class DraftRequest(BaseModel):
    site_id: str
    topic: str
    keyword: str | None = None
    expert_insights: str | None = None


@router.post("/tools/draft", tags=["tools"])
async def draft_preview(req: DraftRequest, user: AuthedUser = Depends(current_user)) -> dict:
    from blogsmith.draft import draft as run_draft
    from blogsmith.outline import outline as run_outline
    from blogsmith.research import research as run_research
    from blogsmith.runner import RunNotFound, build_preview_context

    try:
        ctx = build_preview_context(
            user.uid,
            req.site_id,
            run_input={"topic": req.topic, "keyword": req.keyword, "expert_insights": req.expert_insights},
        )
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    topic = {"title": req.topic, "primary_keyword": req.keyword or req.topic}
    research = await run_research(ctx, topic)
    outline = await run_outline(ctx, topic, research)
    try:
        drafted = await run_draft(ctx, outline, research)
    except LlmUnavailable as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"research": research, "outline": outline, "draft": drafted}


class ImageRequest(BaseModel):
    prompt: str
    style: str | None = None


@router.post("/tools/preview-image", tags=["tools"])
async def preview_image(req: ImageRequest, user: AuthedUser = Depends(current_user)) -> dict:
    from blogsmith.runner import build_preview_context

    ctx = build_preview_context(user.uid)
    if not ctx.images.available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Gemini key configured for image generation.",
        )
    image = await ctx.images.generate(req.prompt, style=req.style)
    if image is None:
        raise HTTPException(status_code=502, detail="Image generation failed.")
    b64 = base64.b64encode(image.data).decode()
    return {"mime_type": image.mime_type, "image_data_url": f"data:{image.mime_type};base64,{b64}"}
