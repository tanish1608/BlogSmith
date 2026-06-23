"""Fake LLM + image clients for pipeline tests (no network, no API key)."""

from __future__ import annotations

DRAFT_MD = (
    "# DPDPA compliance checklist\n\n"
    "You handle personal data, so the DPDPA applies to you. Here's what to do.\n\n"
    "## Overview\n\n"
    "[[IMAGE: flowchart | DPDPA consent flow | Diagram of the DPDPA consent flow]]\n\n"
    "Consent must be free, specific, and informed.\n\n"
    "## Next steps\n\nAppoint a Data Protection Officer and publish your notice."
)


class FakeLlm:
    """Routes responses by markers found in each stage's authored system prompt."""

    available = True

    async def complete(self, system: str, user: str, *, temperature=None) -> str:
        if "Mermaid" in system:
            return "```mermaid\nflowchart TD\n  A[Collect consent] --> B[Process data]\n```"
        # draft stage
        return DRAFT_MD

    async def complete_json(self, system: str, user: str):
        if "senior SEO content strategist" in system:  # discovery
            return {"topics": [{"title": "DPDPA compliance checklist",
                                "primary_keyword": "dpdpa compliance checklist",
                                "search_intent": "commercial", "buyer_intent_score": 88,
                                "rationale": "high intent", "pillar": "data-privacy"}]}
        if "meticulous research analyst" in system:  # research
            return {"summary": "DPDPA governs personal data in India.",
                    "key_facts": [{"fact": "Consent must be free", "status": "verified",
                                   "source": "DPDPA 2023 s.6"}],
                    "primary_sources": [{"name": "DPDPA 2023", "url": None, "why": "the statute"}],
                    "statistics": [], "angles_competitors_miss": ["DPO appointment timing"]}
        if "SEO content architect" in system:  # outline
            return {"h1": "DPDPA compliance checklist", "target_keyword": "dpdpa compliance checklist",
                    "search_intent": "commercial", "estimated_word_count": 1000,
                    "sections": [{"heading": "Overview", "level": 2, "purpose": "answer",
                                  "talking_points": ["consent"], "internal_link": None,
                                  "visual": {"type": "flowchart", "shows": "consent flow"},
                                  "expert_insight_slot": True, "children": []}]}
        if "ruthless editor" in system:  # critique
            return {"edited_markdown": DRAFT_MD,
                    "claims": [{"claim": "Consent must be free", "status": "verified", "note": ""}],
                    "ai_tells_found": [], "fluff_removed": "trimmed intro",
                    "checklist": [{"item": "Keyword in H1", "pass": True, "note": ""}]}
        if "on-page SEO specialist" in system:  # finalize
            return {"title": "DPDPA Compliance Checklist (2026)",
                    "meta_description": "A practical DPDPA compliance checklist for Indian businesses.",
                    "slug": "dpdpa-compliance-checklist",
                    "json_ld": {"@context": "https://schema.org", "@type": "BlogPosting",
                                "headline": "DPDPA Compliance Checklist"},
                    "images": [{"placeholder_index": 0, "type": "flowchart",
                                "generation_prompt": "DPDPA consent flow diagram",
                                "alt_text": "DPDPA consent flow"}]}
        if "B2B social writer" in system:  # distribute
            return {"thread": ["Most Indian SaaS firms are not DPDPA-ready.",
                               "Here's the 5-step checklist 👇", "Full post: {{POST_URL}}"]}
        return {}


class FakeImages:
    """Image generation unavailable → forces the Mermaid fallback path."""

    available = False

    async def generate(self, prompt: str, *, style=None):
        return None
