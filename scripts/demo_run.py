#!/usr/bin/env python
"""Run the full 9-stage pipeline locally, end to end, with no cloud infra.

Uses a real Gemini key if one is available (env GEMINI_API_KEY / GOOGLE_API_KEY /
FALLBACK_GEMINI_KEY), otherwise falls back to the deterministic test fakes so the
pipeline still completes and prints a result. The email gate is auto-approved.

    python scripts/demo_run.py --topic "DPDPA compliance checklist for SaaS"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blogsmith.graph.blog_graph import run_pipeline  # noqa: E402
from blogsmith.graph.context import RunContext  # noqa: E402
from blogsmith.graph.image_model import ImageClient  # noqa: E402
from blogsmith.graph.model import LlmBudget, LlmClient  # noqa: E402

SITE = {
    "domain": "demo.example",
    "brand_voice": "Direct, expert, concrete. No fluff.",
    "custom_prompts": {},
    "image_style": "clean minimal line art, muted palette",
    "pillar_cluster_map": {"data-privacy": ["dpdpa", "consent", "data fiduciary"]},
    "internal_links": [],
    "discovery": {"source": "seed", "seed_topics": ["DPDPA compliance"]},
}


def _gemini_key() -> str | None:
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "FALLBACK_GEMINI_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    return None


def _build_ctx(topic: str, key: str | None) -> RunContext:
    run_input = {
        "topic": topic,
        "keyword": topic,
        "expert_insights": "In a 2025 audit of 40 Indian SaaS firms, 80% had no consent notice.",
        "auto_approve": True,
    }
    if key:
        llm: object = LlmClient(key, LlmBudget())
        images: object = ImageClient(key)
        print(f"→ Using real Gemini ({os.environ.get('TEXT_MODEL', 'gemini-2.0-flash')}).")
    else:
        from tests.fakes import FakeImages, FakeLlm

        llm, images = FakeLlm(), FakeImages()
        print("→ No Gemini key found — using deterministic fakes.")
    return RunContext(
        uid="demo", site_id="demo", run_id="demo",
        site=SITE, run_input=run_input,
        llm=llm, images=images, auto_approve=True, persist_enabled=False,
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="DPDPA compliance checklist for SaaS")
    args = parser.parse_args()

    ctx = _build_ctx(args.topic, _gemini_key())
    state = await run_pipeline(ctx)

    print("\n" + "=" * 70)
    print("STATUS:", state.get("status"))
    final = state.get("final", {})
    print("TITLE:", final.get("title"))
    print("META :", final.get("meta_description"))
    print("SLUG :", final.get("slug"))
    print("=" * 70)
    print((state.get("visuals", {}) or {}).get("markdown", "")[:2000])
    print("\n--- LinkedIn thread ---")
    for i, post in enumerate((state.get("distribution", {}) or {}).get("linkedin_thread", []), 1):
        print(f"{i}. {post}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
