"""API keys — read from the local environment (.env).

Single local workspace, no per-user storage: the Gemini / LangSmith / SERP keys
come straight from settings. :func:`get_keys` feeds the run executor; the account
endpoint shows :func:`masked_keys` so the dashboard can indicate what's set.
"""

from __future__ import annotations

from blogsmith.config import get_settings

KEY_FIELDS = ("gemini_key", "langsmith_key", "serp_key")


def get_keys() -> dict[str, str | None]:
    """The effective keys for run execution (from .env)."""
    s = get_settings()
    return {
        "gemini_key": s.gemini_key,
        "langsmith_key": s.langsmith_api_key,
        "serp_key": s.serp_api_key,
    }


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    return "••••" + value[-4:] if len(value) > 4 else "••••"


def masked_keys() -> dict[str, str | None]:
    """Display-safe map of which keys are configured (never the plaintext)."""
    return {field: _mask(value) for field, value in get_keys().items()}
