"""Central configuration.

Settings are read from the environment (and an optional ``.env`` file). Every
value has a local-dev default so the whole app boots against the Firebase
emulator with zero cloud setup — the CleanCrawl "local-first, zero infra" rule.
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
    public_base_url: str = Field(
        default="http://localhost:8000",
        description="Externally reachable base URL — used to build email approval links.",
    )

    # ── Firebase ──────────────────────────────────────────────────────────────
    firebase_project_id: str = Field(default="blogsmith-local")
    firebase_storage_bucket: str = Field(default="blogsmith-local.appspot.com")
    # Set by `firebase emulators:start`; presence flips the SDK into emulator mode.
    firestore_emulator_host: str | None = Field(default=None)
    firebase_auth_emulator_host: str | None = Field(default=None)
    storage_emulator_host: str | None = Field(default=None)
    # Optional path to a service-account JSON (prod). Empty → application default creds.
    google_application_credentials: str | None = Field(default=None)

    # ── Auth ──────────────────────────────────────────────────────────────────
    # When true (dev), API calls skip Firebase ID-token verification and use a
    # fixed dev uid. NEVER enable in prod.
    auth_disabled: bool = Field(default=False)
    dev_uid: str = Field(default="dev-user")
    dev_email: str = Field(default="dev@example.com")

    # ── Secrets / crypto ──────────────────────────────────────────────────────
    # urlsafe base64 32-byte Fernet key, used to encrypt BYOK provider keys at
    # rest in Firestore. A throwaway key is generated for dev if unset.
    key_encryption_key: str | None = Field(default=None)

    # ── LLM defaults (per-user key is BYOK; these are model ids/budgets) ───────
    text_model: str = Field(default="gemini-2.0-flash")
    image_model: str = Field(default="gemini-2.0-flash-exp-image-generation")
    llm_run_budget: int = Field(default=60, description="Max LLM calls per blog run.")
    # Global fallback key for local experimentation only; real users bring their own.
    fallback_gemini_key: str | None = Field(default=None)

    # ── LangSmith (optional observability) ────────────────────────────────────
    langsmith_api_key: str | None = Field(default=None)
    langsmith_project: str = Field(default="blogsmith")

    # ── Run dispatch ──────────────────────────────────────────────────────────
    dispatch_to_cloud_run: bool = Field(default=False)
    cloud_run_job_name: str = Field(default="blogsmith-job")
    cloud_run_region: str = Field(default="us-central1")

    # ── Scheduler ─────────────────────────────────────────────────────────────
    # Shared secret Cloud Scheduler must present to POST /scheduler/tick.
    scheduler_secret: str = Field(default="dev-scheduler-secret")

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
