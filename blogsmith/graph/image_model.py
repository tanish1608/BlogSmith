"""Gemini image generation + Mermaid fallback.

The Visuals stage asks this client to render each planned image. When image
generation is unavailable (no key, quota, or API error), diagram/flowchart/chart
placements degrade to a Mermaid code block produced by the text model, and photo
placements degrade to nothing (the placeholder is dropped). The pipeline always
completes — the CleanCrawl graceful-degradation rule.
"""

from __future__ import annotations

import asyncio
import logging
import re

from blogsmith.config import get_settings
from blogsmith.graph.model import LlmClient
from blogsmith.prompts.defaults import MERMAID_FALLBACK_SYSTEM, VISUALS_SYSTEM

logger = logging.getLogger(__name__)

# Types we can express as Mermaid when image gen is down.
_DIAGRAMMABLE = {"flowchart", "diagram", "chart"}


class GeneratedImage:
    def __init__(self, data: bytes, mime_type: str) -> None:
        self.data = data
        self.mime_type = mime_type


class ImageClient:
    def __init__(self, api_key: str | None, model: str | None = None) -> None:
        self.api_key = api_key
        self.model = model or get_settings().image_model
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _genai(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _generate_sync(self, prompt: str, style: str | None) -> GeneratedImage | None:
        from google.genai import types

        full_prompt = VISUALS_SYSTEM + "\n\n" + prompt
        if style:
            full_prompt += f"\n\nVisual style: {style}"
        resp = self._genai().models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
        )
        for candidate in getattr(resp, "candidates", []) or []:
            for part in getattr(candidate.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    return GeneratedImage(inline.data, inline.mime_type or "image/png")
        return None

    async def generate(self, prompt: str, *, style: str | None = None) -> GeneratedImage | None:
        """Generate one image. Returns None on any failure (caller falls back)."""
        if not self.available:
            return None
        try:
            return await asyncio.to_thread(self._generate_sync, prompt, style)
        except Exception as exc:  # noqa: BLE001 — any failure → graceful fallback
            logger.warning("Image generation failed (%s); will fall back.", exc)
            return None


async def mermaid_fallback(llm: LlmClient, image_type: str, description: str) -> str | None:
    """Produce a Mermaid code block for a diagrammable placement, or None."""
    if image_type not in _DIAGRAMMABLE or not llm.available:
        return None
    try:
        text = await llm.complete(
            MERMAID_FALLBACK_SYSTEM,
            f"Type: {image_type}\nDescription: {description}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mermaid fallback failed: %s", exc)
        return None
    match = re.search(r"```mermaid.*?```", text, re.DOTALL)
    return match.group(0) if match else None
