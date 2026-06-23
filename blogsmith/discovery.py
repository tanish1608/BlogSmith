"""Stage 1 — Discovery.

Pulls candidate topic signals from pluggable sources, then ranks them by buyer
intent. The free default mixes the site's seed topics with scraped Google
autocomplete; GSC and paid-SERP adapters share the same interface and are stubbed
until a user wires up credentials. Ranking uses the LLM when available and falls
back to a deterministic intent heuristic.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from blogsmith.graph.context import RunContext
from blogsmith.graph.model import LlmUnavailable
from blogsmith.models import DiscoverySource
from blogsmith.prompts import build_system_prompt

logger = logging.getLogger(__name__)

# Buyer-intent signal words for the heuristic ranker.
_HIGH_INTENT = ("best", "vs", "pricing", "cost", "alternative", "review", "how to", "checklist", "template", "for")


class DiscoveryAdapter(Protocol):
    async def signals(self, seed_topics: list[str], config: dict) -> list[str]: ...


class SeedAutocompleteAdapter:
    """Free default: seed topics + Google autocomplete expansions."""

    async def signals(self, seed_topics: list[str], config: dict) -> list[str]:
        out: list[str] = list(seed_topics)
        async with httpx.AsyncClient(timeout=5.0) as http:
            for seed in seed_topics:
                out.extend(await self._autocomplete(http, seed))
        # De-dupe, preserve order.
        seen: set[str] = set()
        return [s for s in out if not (s.lower() in seen or seen.add(s.lower()))]

    async def _autocomplete(self, http: httpx.AsyncClient, query: str) -> list[str]:
        try:
            resp = await http.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client": "firefox", "q": query},
            )
            data = resp.json()
            return list(data[1]) if isinstance(data, list) and len(data) > 1 else []
        except Exception as exc:  # noqa: BLE001 — autocomplete is best-effort
            logger.info("Autocomplete failed for %r: %s", query, exc)
            return []


class GscAdapter:
    """Stub — returns nothing until Google Search Console OAuth is wired up."""

    async def signals(self, seed_topics: list[str], config: dict) -> list[str]:
        logger.info("GSC adapter not configured; skipping.")
        return list(seed_topics)


class SerpAdapter:
    """Stub — returns nothing until a paid SERP key is wired up."""

    async def signals(self, seed_topics: list[str], config: dict) -> list[str]:
        logger.info("SERP adapter not configured; skipping.")
        return list(seed_topics)


_ADAPTERS = {
    DiscoverySource.SEED: SeedAutocompleteAdapter,
    DiscoverySource.GSC: GscAdapter,
    DiscoverySource.SERP: SerpAdapter,
}


def _heuristic_rank(candidates: list[str], pillars: dict[str, list[str]], limit: int) -> list[dict]:
    ranked = []
    for cand in candidates:
        low = cand.lower()
        score = 40
        score += sum(8 for kw in _HIGH_INTENT if kw in low)
        pillar = next(
            (p for p, clusters in pillars.items() if any(c.lower() in low for c in clusters)),
            None,
        )
        if pillar:
            score += 15
        ranked.append(
            {
                "title": cand,
                "primary_keyword": cand,
                "search_intent": "commercial" if score >= 60 else "informational",
                "buyer_intent_score": min(100, score),
                "rationale": "heuristic intent score",
                "pillar": pillar,
            }
        )
    ranked.sort(key=lambda t: t["buyer_intent_score"], reverse=True)
    return ranked[:limit]


async def discover(ctx: RunContext, limit: int = 8) -> dict:
    """Return the discovery slice with a ranked topic list and a selected topic."""
    run_input = ctx.run_input

    # Explicit topic short-circuits discovery.
    if run_input.get("topic"):
        selected = {
            "title": run_input["topic"],
            "primary_keyword": run_input.get("keyword") or run_input["topic"],
            "search_intent": "informational",
            "buyer_intent_score": 100,
            "rationale": "explicitly requested",
            "pillar": None,
        }
        return {"source": "manual", "signals": [], "topics": [selected], "selected": selected}

    disc_cfg = ctx.site.get("discovery", {}) or {}
    source = DiscoverySource(disc_cfg.get("source", DiscoverySource.SEED))
    seeds = disc_cfg.get("seed_topics", []) or []
    adapter = _ADAPTERS[source]()
    candidates = await adapter.signals(seeds, disc_cfg)

    if not candidates:
        # Nothing to work with — surface a clear, recoverable state.
        return {"source": source.value, "signals": [], "topics": [], "selected": None}

    pillars = ctx.site.get("pillar_cluster_map", {}) or {}
    topics: list[dict] = []

    if ctx.llm.available:
        try:
            user = (
                f"Site domain: {ctx.site.get('domain')}\n"
                f"Pillar/cluster map: {pillars}\n"
                f"Candidate signals: {candidates}\n"
                f"Return at most {limit} topics."
            )
            system = build_system_prompt(
                "discovery", brand_voice=ctx.brand_voice, custom=ctx.custom_prompt("discovery")
            )
            parsed = await ctx.llm.complete_json(system, user)
            topics = parsed.get("topics", []) if isinstance(parsed, dict) else []
        except (LlmUnavailable, Exception) as exc:  # noqa: BLE001
            logger.warning("LLM ranking failed (%s); using heuristic.", exc)

    if not topics:
        topics = _heuristic_rank(candidates, pillars, limit)

    selected = topics[0] if topics else None
    return {
        "source": source.value,
        "signals": candidates[:50],
        "topics": topics,
        "selected": selected,
    }
