"""Deterministic SEO scoring.

Same page → same score, always (the CleanCrawl "deterministic score, LLM only
narrates" principle). The critique stage merges these objective checks with the
model's editorial pass; the score never depends on LLM availability.
"""

from __future__ import annotations

from dataclasses import dataclass

from blogsmith.markdown_utils import first_h1, strip_markdown

# A few of the banned AI-tells, checked deterministically.
_AI_TELLS = (
    "delve",
    "moreover",
    "furthermore",
    "it's important to note",
    "in conclusion",
    "in today's fast-paced world",
    "navigating the world of",
    "game-changer",
    "seamless",
    "in the ever-evolving",
)


@dataclass
class SeoCheck:
    item: str
    passed: bool
    note: str = ""

    def as_dict(self) -> dict:
        return {"item": self.item, "pass": self.passed, "note": self.note}


def evaluate(markdown: str, keyword: str | None) -> dict:
    """Return {score, checks[], word_count, ai_tells[]} for an article."""
    text = strip_markdown(markdown)
    words = text.split()
    word_count = len(words)
    first_100 = " ".join(words[:100]).lower()
    h1 = (first_h1(markdown) or "").lower()
    kw = (keyword or "").lower().strip()
    lower_md = markdown.lower()

    checks: list[SeoCheck] = []

    if kw:
        checks.append(SeoCheck("Keyword in H1", kw in h1, h1 or "no H1 found"))
        checks.append(SeoCheck("Keyword in first 100 words", kw in first_100))
    checks.append(SeoCheck("Has an H1", bool(h1), h1))
    checks.append(
        SeoCheck("Has H2 sections", "\n## " in markdown or markdown.startswith("## "))
    )
    checks.append(SeoCheck("Has an internal/any link", "](" in markdown))
    checks.append(
        SeoCheck(
            "Sufficient length (>=600 words)",
            word_count >= 600,
            f"{word_count} words",
        )
    )

    tells_found = [t for t in _AI_TELLS if t in lower_md]
    checks.append(
        SeoCheck("No common AI-tell phrases", not tells_found, ", ".join(tells_found))
    )

    passed = sum(1 for c in checks if c.passed)
    score = round(100 * passed / len(checks)) if checks else 0

    return {
        "score": score,
        "word_count": word_count,
        "ai_tells": tells_found,
        "checks": [c.as_dict() for c in checks],
    }
