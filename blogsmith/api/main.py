"""FastAPI app factory — fully local.

Initialises the SQLite store on startup, starts the in-process cadence scheduler,
serves generated images from the local media folder, mounts every router, and
serves the React dashboard from ``frontend/dist`` when built (falling back to
API-only mode with Swagger at ``/docs``).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from blogsmith import __version__, store
from blogsmith.api.routers import account, runs, scheduler, sites, tools
from blogsmith.config import get_settings
from blogsmith.scheduler_local import scheduler_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    settings = get_settings()
    store.init_db()
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
        logger.info("LangSmith tracing enabled (project=%s).", settings.langsmith_project)

    task: asyncio.Task | None = None
    if settings.scheduler_enabled:
        task = asyncio.create_task(scheduler_loop())

    logger.info("BlogSmith %s started (env=%s, db=%s).", __version__, settings.app_env, settings.db_path)
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BlogSmith",
        version=__version__,
        description=(
            "Local agentic blogging service — a 9-stage LangGraph pipeline "
            "(Discovery → Research → Outline → Draft → Critique → review gate → "
            "Finalize → Visuals → Distribute) that writes human-like, SEO-strong "
            "posts with Gemini image generation. SQLite store, no auth, no cloud."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(tools.router)
    app.include_router(account.router)
    app.include_router(sites.router)
    app.include_router(runs.router)
    app.include_router(scheduler.router)

    _mount_media(app, settings)
    _mount_frontend(app)
    return app


def _mount_media(app: FastAPI, settings) -> None:  # noqa: ANN001
    media_dir = Path(settings.images_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        settings.media_url_prefix,
        StaticFiles(directory=str(media_dir)),
        name="media",
    )


def _mount_frontend(app: FastAPI) -> None:
    if _FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="ui")
        logger.info("Serving dashboard from %s", _FRONTEND_DIST)
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> JSONResponse:
            return JSONResponse(
                {
                    "service": "BlogSmith",
                    "version": __version__,
                    "docs": "/docs",
                    "note": "Dashboard not built. Run `cd frontend && npm run build`.",
                }
            )


app = create_app()
