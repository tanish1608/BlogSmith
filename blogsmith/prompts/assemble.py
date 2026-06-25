"""Prompt assembly — layer site config onto the authored defaults.

Final system prompt for a stage =
    authored default
    + human-like writing rules (writing stages only)
    + site brand voice (if set)
    + site per-stage custom prompt (if set)

The assembled prompt is logged to the run's stage slice so every post is
reproducible and auditable (which is why ``PROMPT_VERSION`` is bumped whenever
the defaults change).
"""

from __future__ import annotations

from blogsmith.prompts.defaults import (
    HUMAN_LIKE_RULES,
    STAGE_DEFAULTS,
    WRITING_STAGES,
)

# Bump when the authored defaults change materially (audit / reproducibility).
PROMPT_VERSION = "2026-06-25.1"


def build_system_prompt(
    stage: str,
    *,
    brand_voice: str | None = None,
    custom: str | None = None,
) -> str:
    """Assemble the system prompt for ``stage``.

    Args:
        stage: one of the keys in ``STAGE_DEFAULTS``.
        brand_voice: the site's global voice rules (applied to every stage).
        custom: the site's per-stage custom prompt addition.
    """
    base = STAGE_DEFAULTS.get(stage)
    if base is None:
        raise KeyError(f"No default prompt for stage {stage!r}")

    parts = [base.strip()]

    if stage in WRITING_STAGES:
        parts.append(HUMAN_LIKE_RULES.strip())

    if brand_voice and brand_voice.strip():
        parts.append("BRAND VOICE (match this exactly):\n" + brand_voice.strip())

    if custom and custom.strip():
        parts.append("ADDITIONAL INSTRUCTIONS FOR THIS SITE:\n" + custom.strip())

    return "\n\n".join(parts)
