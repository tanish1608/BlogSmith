"""LLM client (Gemini default) + a run-level call budget.

Heuristic-first, CleanCrawl-style: the model is an enhancement layer. Stages that
can degrade (discovery, research) check ``available`` / catch ``LlmUnavailable``
and fall back to deterministic behaviour. The writer stages (draft/critique)
require a working key and fail the run loudly if it's missing — never a silent
empty post.

Calls run in worker threads so they don't block the event loop (the CleanCrawl
"non-blocking LLM calls" fix).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from blogsmith.config import get_settings

logger = logging.getLogger(__name__)


class LlmUnavailable(RuntimeError):
    """Raised when no key is configured or the per-run budget is exhausted."""


class LlmBudget:
    """Caps total LLM calls per blog run (CleanCrawl run-level budget)."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit if limit is not None else get_settings().llm_run_budget
        self.used = 0

    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def consume(self) -> None:
        if self.used >= self.limit:
            raise LlmUnavailable(f"LLM run budget exhausted ({self.limit} calls).")
        self.used += 1


def _extract_json(text: str):
    """Best-effort JSON extraction from a model response (handles ``` fences/prose)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the first balanced { } or [ ] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("Model did not return parseable JSON.")


class LlmClient:
    """Thin wrapper over ChatGoogleGenerativeAI with budget + JSON helpers."""

    def __init__(
        self,
        api_key: str | None,
        budget: LlmBudget,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> None:
        self.api_key = api_key
        self.budget = budget
        self.model = model or get_settings().text_model
        self.temperature = temperature
        self._chat = None  # lazily constructed

    @property
    def available(self) -> bool:
        return bool(self.api_key) and self.budget.remaining() > 0

    def _client(self):
        if self._chat is None:
            if not self.api_key:
                raise LlmUnavailable("No Gemini API key configured for this user.")
            from langchain_google_genai import ChatGoogleGenerativeAI

            self._chat = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=self.api_key,
                temperature=self.temperature,
            )
        return self._chat

    def _invoke(self, system: str, user: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = self._client().invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        content = resp.content
        if isinstance(content, list):  # some providers return content parts
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return content

    async def complete(self, system: str, user: str, *, temperature: float | None = None) -> str:
        """Return raw text. Raises LlmUnavailable on missing key/budget."""
        if not self.api_key:
            raise LlmUnavailable("No Gemini API key configured for this user.")
        self.budget.consume()
        if temperature is not None and temperature != self.temperature:
            self.temperature = temperature
            self._chat = None
        return await asyncio.to_thread(self._invoke, system, user)

    async def complete_json(self, system: str, user: str) -> dict | list:
        """Complete and parse JSON, retrying once with a stricter instruction."""
        raw = await self.complete(system, user)
        try:
            return _extract_json(raw)
        except ValueError:
            logger.warning("First JSON parse failed; retrying with strict instruction.")
            raw = await self.complete(
                system,
                user + "\n\nReturn ONLY valid JSON. No prose, no code fences.",
            )
            return _extract_json(raw)
