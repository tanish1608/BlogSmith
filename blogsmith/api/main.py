"""FastAPI app factory.

Boots Firebase on startup, mounts every router, and serves the React dashboard
from ``frontend/dist`` when it has been built (falling back to API-only mode with
Swagger at ``/docs`` — the CleanCrawl behaviour).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from blogsmith import __version__
from blogsmith.api.routers import account, runs, scheduler, sites, tools
from blogsmith.config import get_settings
from blogsmith.firestore_db import init_firebase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    settings = get_settings()
    init_firebase()
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
        logger.info("LangSmith tracing enabled (project=%s).", settings.langsmith_project)
    logger.info("BlogSmith %s started (env=%s).", __version__, settings.app_env)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="BlogSmith",
        version=__version__,
        description=(
            "Agentic blogging service — a 9-stage LangGraph pipeline "
            "(Discovery → Research → Outline → Draft → Critique → human email "
            "gate → Finalize → Visuals → Distribute) that writes human-like, "
            "SEO-strong posts with Gemini image generation."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dashboard + Swagger; tighten per-deployment if needed
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(tools.router)
    app.include_router(account.router)
    app.include_router(sites.router)
    app.include_router(runs.router)
    app.include_router(scheduler.router)

    _mount_frontend(app)
    return app


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
