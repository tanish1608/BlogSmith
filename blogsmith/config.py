"""Central configuration — fully local, no cloud.

Settings come from the environment (and an optional ``.env``). Everything has a
local default so the app boots with zero setup: a SQLite file for data, a local
folder for generated images, and API keys read straight from ``.env``. There is
no auth and no Firebase — a single shared local workspace.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Environment ───────────────────────────────────────────────────────────
    app_env: str = Field(default="dev", description="dev | prod")
    public_base_url: str = Field(default="http://localhost:8000")

    # ── Local storage ─────────────────────────────────────────────────────────
    db_path: str = Field(default="blogsmith.db", description="SQLite file for sites/runs.")
    images_dir: str = Field(default="media", description="Folder for generated images.")
    media_url_prefix: str = Field(default="/media", description="URL prefix images are served under.")

    # ── API keys (read from .env — single local user) ─────────────────────────
    gemini_api_key: str | None = Field(default=None, description="Google Gemini API key (text + images).")
    # Back-compat alias; either env var works.
    fallback_gemini_key: str | None = Field(default=None)
    serp_api_key: str | None = Field(default=None)
    langsmith_api_key: str | None = Field(default=None)
    langsmith_project: str = Field(default="blogsmith")

    # ── LLM ───────────────────────────────────────────────────────────────────
    text_model: str = Field(default="gemini-2.0-flash")
    image_model: str = Field(default="gemini-2.0-flash-exp-image-generation")
    llm_run_budget: int = Field(default=60, description="Max LLM calls per blog run.")

    # ── Local scheduler ───────────────────────────────────────────────────────
    scheduler_enabled: bool = Field(default=True, description="Run the in-process cadence scheduler.")
    scheduler_interval_seconds: int = Field(default=60, description="How often the scheduler ticks.")

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def gemini_key(self) -> str | None:
        """The effective Gemini key (primary env var, then the alias)."""
        return self.gemini_api_key or self.fallback_gemini_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
