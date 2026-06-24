"""CSV import/export for site config and bulk blog-run topics.

Two flat CSV shapes, both designed to survive a round-trip through Excel / Google
Sheets / Numbers (which prepend a "Table 1" line, append empty trailing columns,
and quote freely):

1. **Site config** — a vertical ``field,value`` sheet. The user downloads their
   site's current config, edits the values, and re-uploads. ``name`` and
   ``domain`` are shown for reference but are LOCKED — never applied on import.

2. **Blog runs** — a row-per-topic sheet with ``topic, primary_keywords,
   expert_insights`` columns. Each row becomes one queued run.
"""

from __future__ import annotations

import csv
import io
from typing import Any

# ── shared helpers ────────────────────────────────────────────────────────────


def _norm(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")


def _split_list(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def _truthy(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _rows(text: str) -> list[list[str]]:
    """Parse CSV text into rows with trailing empty cells trimmed."""
    out: list[list[str]] = []
    for row in csv.reader(io.StringIO(text)):
        while row and not (row[-1] or "").strip():
            row.pop()
        out.append(row)
    return out


# ── 1. Site config CSV ────────────────────────────────────────────────────────

# Order matters — this is the on-screen layout of the template.
# (csv_field, help text shown in a trailing column)
_CONFIG_LAYOUT: list[tuple[str, str]] = [
    ("name", "LOCKED — for reference only, not applied on upload"),
    ("domain", "LOCKED — for reference only, not applied on upload"),
    ("brand_voice", "Global voice/tone, e.g. 'Direct, expert, concrete. No fluff.'"),
    ("image_style", "Visual style for generated images"),
    ("content_type", "guide | teardown | explainer | comparison | checklist | opinion | tutorial"),
    ("default_tags", "comma-separated tags added to every post"),
    ("author_name", "Byline name in the MDX frontmatter"),
    ("author_role", "Byline role, e.g. 'Founder · Lead Architect'"),
    ("author_url", "Byline link, e.g. '/the-lab'"),
    ("prompt_brand_voice", "Custom prompt addition applied to every stage"),
    ("prompt_discovery", "Custom prompt addition for the discovery stage"),
    ("prompt_research", "Custom prompt addition for the research stage"),
    ("prompt_outline", "Custom prompt addition for the outline stage"),
    ("prompt_draft", "Custom prompt addition for the draft stage"),
    ("prompt_critique", "Custom prompt addition for the critique stage"),
    ("prompt_finalize", "Custom prompt addition for the finalize stage"),
    ("prompt_visuals", "Custom prompt addition for the visuals stage"),
    ("prompt_distribute", "Custom prompt addition for the distribute stage"),
    ("discovery_source", "seed | autocomplete | gsc | serp"),
    ("discovery_seed_topics", "comma-separated seed topics"),
    ("schedule_enabled", "true | false"),
    ("schedule_cadence", "daily | weekly"),
    ("schedule_times", "comma-separated HH:MM local times, e.g. '09:00, 17:00'"),
    ("schedule_timezone", "IANA tz, e.g. 'America/New_York'"),
    ("schedule_count_per_run", "blogs to enqueue each fire (integer)"),
]

_PROMPT_STAGES = (
    "brand_voice", "discovery", "research", "outline", "draft",
    "critique", "finalize", "visuals", "distribute",
)


def config_to_csv(site: dict[str, Any]) -> str:
    """Render a site's current config as a downloadable ``field,value`` CSV."""
    site = site or {}
    author = site.get("author") or {}
    prompts = site.get("custom_prompts") or {}
    discovery = site.get("discovery") or {}
    schedule = site.get("schedule") or {}

    values: dict[str, str] = {
        "name": str(site.get("name", "")),
        "domain": str(site.get("domain", "")),
        "brand_voice": str(site.get("brand_voice") or ""),
        "image_style": str(site.get("image_style") or ""),
        "content_type": str(site.get("content_type") or "guide"),
        "default_tags": ", ".join(site.get("default_tags") or []),
        "author_name": str(author.get("name") or ""),
        "author_role": str(author.get("role") or ""),
        "author_url": str(author.get("url") or ""),
        "discovery_source": str(discovery.get("source") or "seed"),
        "discovery_seed_topics": ", ".join(discovery.get("seed_topics") or []),
        "schedule_enabled": "true" if schedule.get("enabled") else "false",
        "schedule_cadence": str(schedule.get("cadence") or "daily"),
        "schedule_times": ", ".join(schedule.get("times") or ["09:00"]),
        "schedule_timezone": str(schedule.get("timezone") or "UTC"),
        "schedule_count_per_run": str(schedule.get("count_per_run") or 1),
    }
    for stage in _PROMPT_STAGES:
        values[f"prompt_{stage}"] = str(prompts.get(stage) or "")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["field", "value", "help"])
    for field, help_text in _CONFIG_LAYOUT:
        w.writerow([field, values.get(field, ""), help_text])
    return buf.getvalue()


def parse_config_csv(text: str) -> dict[str, Any]:
    """Parse a config CSV into a partial site-update dict (name/domain ignored).

    Only fields the user actually filled are returned, so re-uploading a template
    never clobbers existing config with blanks. Nested objects (author,
    custom_prompts, discovery, schedule) are only included when at least one of
    their fields is present.
    """
    raw: dict[str, str] = {}
    for row in _rows(text):
        if len(row) < 2:
            continue
        key = _norm(row[0])
        if key in {"field", ""}:  # header row / blank
            continue
        raw[key] = row[1].strip()

    updates: dict[str, Any] = {}

    def take(field: str) -> str | None:
        v = raw.get(field)
        return v if v not in (None, "") else None

    # name / domain are intentionally NOT read — they are locked.
    for field in ("brand_voice", "image_style", "content_type"):
        if (v := take(field)) is not None:
            updates[field] = v
    if "default_tags" in raw:
        updates["default_tags"] = _split_list(raw["default_tags"])

    author = {
        k: raw[f"author_{k}"].strip()
        for k in ("name", "role", "url")
        if raw.get(f"author_{k}")
    }
    if author:
        updates["author"] = author

    prompts = {
        stage: raw[f"prompt_{stage}"]
        for stage in _PROMPT_STAGES
        if raw.get(f"prompt_{stage}")
    }
    if prompts:
        updates["custom_prompts"] = prompts

    discovery: dict[str, Any] = {}
    if (v := take("discovery_source")) is not None:
        discovery["source"] = v.lower()
    if "discovery_seed_topics" in raw:
        discovery["seed_topics"] = _split_list(raw["discovery_seed_topics"])
    if discovery:
        updates["discovery"] = discovery

    schedule: dict[str, Any] = {}
    if "schedule_enabled" in raw:
        schedule["enabled"] = _truthy(raw["schedule_enabled"])
    if (v := take("schedule_cadence")) is not None:
        schedule["cadence"] = v.lower()
    if "schedule_times" in raw:
        schedule["times"] = _split_list(raw["schedule_times"])
    if (v := take("schedule_timezone")) is not None:
        schedule["timezone"] = v
    if (v := take("schedule_count_per_run")) is not None:
        try:
            schedule["count_per_run"] = int(float(v))
        except ValueError:
            pass
    if schedule:
        updates["schedule"] = schedule

    return updates


# ── 2. Blog-run topics CSV ────────────────────────────────────────────────────

# Accepted header aliases → canonical field.
_RUN_ALIASES = {
    "topic": "topic", "title": "topic", "blog": "topic", "blog_topic": "topic",
    "primary_keywords": "keyword", "primary_keyword": "keyword",
    "keywords": "keyword", "keyword": "keyword", "target_keyword": "keyword",
    "expert_insights": "expert_insights", "expert_insight": "expert_insights",
    "insights": "expert_insights", "notes": "notes",
}

RUN_TEMPLATE_HEADERS = ["topic", "primary_keywords", "expert_insights"]


def runs_template_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(RUN_TEMPLATE_HEADERS)
    w.writerow([
        "Why most enterprise AI pilots fail after the demo",
        "enterprise AI pilots, production AI, AI strategy",
        "The real failure is rarely the model — it is workflow fit, data readiness, and missing eval loops.",
    ])
    w.writerow([
        "RAG systems that do not leak company data",
        "private RAG, vector database, enterprise search",
        "A safe RAG system needs document permissions, source citations, and audit logs.",
    ])
    return buf.getvalue()


def parse_runs_csv(text: str) -> list[dict[str, Any]]:
    """Parse a topics CSV into a list of run-create payload dicts.

    Tolerates a leading junk line (e.g. 'Table 1'), trailing empty columns, and
    flexible header names. The first row containing a recognizable 'topic' column
    is treated as the header. The first primary keyword becomes the run's primary
    ``keyword``; any extras are appended to ``notes``.
    """
    rows = _rows(text)
    header_idx = -1
    header: list[str] = []
    for i, row in enumerate(rows):
        mapped = [_RUN_ALIASES.get(_norm(c), "") for c in row]
        if "topic" in mapped:
            header_idx = i
            header = mapped
            break
    if header_idx < 0:
        return []

    runs: list[dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        record: dict[str, str] = {}
        for col, value in zip(header, row, strict=False):
            if col and value.strip() and not record.get(col):
                record[col] = value.strip()
        topic = record.get("topic")
        if not topic:
            continue

        keywords = _split_list(record.get("keyword", ""))
        notes_parts = [record["notes"]] if record.get("notes") else []
        if len(keywords) > 1:
            notes_parts.append("Secondary keywords: " + ", ".join(keywords[1:]))

        runs.append({
            "topic": topic,
            "keyword": keywords[0] if keywords else None,
            "expert_insights": record.get("expert_insights"),
            "notes": "\n".join(notes_parts) or None,
        })
    return runs
