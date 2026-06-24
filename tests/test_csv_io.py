"""CSV import/export: messy real-world parsing + config round-trip + HTTP."""

from __future__ import annotations

from blogsmith.csv_io import (
    config_to_csv,
    parse_config_csv,
    parse_runs_csv,
    runs_template_csv,
)

# A Numbers/Sheets export: leading "Table 1" line, UPPERCASE headers, trailing
# empty columns, multi-keyword quoted cells — exactly the user's blogs-data.csv.
MESSY_RUNS_CSV = (
    "Table 1\n"
    "TOPIC,PRIMARY KEYWORDS,EXPERT INSIGHTS,,,,\n"
    'Why most enterprise AI pilots fail,"enterprise AI pilots, production AI, AI strategy",'
    '"The real failure is rarely the model.",,,,\n'
    'RAG systems that do not leak data,"private RAG, vector database","Needs permissions and logs.",,,,\n'
)


def test_parse_runs_csv_handles_messy_export():
    rows = parse_runs_csv(MESSY_RUNS_CSV)
    assert len(rows) == 2

    first = rows[0]
    assert first["topic"] == "Why most enterprise AI pilots fail"
    # First keyword becomes the primary; extras spill into notes.
    assert first["keyword"] == "enterprise AI pilots"
    assert "Secondary keywords: production AI, AI strategy" in first["notes"]
    assert first["expert_insights"].startswith("The real failure")

    assert rows[1]["topic"] == "RAG systems that do not leak data"
    assert rows[1]["keyword"] == "private RAG"


def test_parse_runs_csv_empty_returns_nothing():
    assert parse_runs_csv("not,a,topics,file\n1,2,3,4") == []


def test_runs_template_is_parseable():
    rows = parse_runs_csv(runs_template_csv())
    assert len(rows) == 2
    assert all(r["topic"] for r in rows)


def test_config_csv_round_trip_preserves_values():
    site = {
        "name": "Acme", "domain": "acme.example",
        "brand_voice": "Direct, expert.",
        "content_type": "teardown",
        "default_tags": ["ai", "rag"],
        "author": {"name": "Founder", "role": "Lead", "url": "/lab"},
        "custom_prompts": {"draft": "Be bold."},
        "discovery": {"source": "seed", "seed_topics": ["dpdpa"]},
        "schedule": {"enabled": True, "cadence": "weekly", "times": ["08:00", "17:00"],
                     "timezone": "Asia/Kolkata", "count_per_run": 3},
    }
    parsed = parse_config_csv(config_to_csv(site))

    assert parsed["brand_voice"] == "Direct, expert."
    assert parsed["content_type"] == "teardown"
    assert parsed["default_tags"] == ["ai", "rag"]
    assert parsed["author"] == {"name": "Founder", "role": "Lead", "url": "/lab"}
    assert parsed["custom_prompts"]["draft"] == "Be bold."
    assert parsed["discovery"]["seed_topics"] == ["dpdpa"]
    assert parsed["schedule"]["enabled"] is True
    assert parsed["schedule"]["times"] == ["08:00", "17:00"]
    assert parsed["schedule"]["count_per_run"] == 3


def test_config_csv_never_returns_name_or_domain():
    parsed = parse_config_csv(config_to_csv({"name": "Acme", "domain": "acme.example"}))
    assert "name" not in parsed
    assert "domain" not in parsed


# ── HTTP ──────────────────────────────────────────────────────────────────────


def _make_site(client) -> str:
    r = client.post("/sites", json={"name": "Acme", "domain": "acme.example"})
    assert r.status_code == 201
    return r.json()["id"]


def test_config_csv_upload_locks_name_and_domain(client):
    site_id = _make_site(client)
    csv_text = (
        "field,value,help\n"
        "name,HACKED,x\n"
        "domain,evil.example,x\n"
        "brand_voice,New voice,x\n"
        "content_type,explainer,x\n"
    )
    r = client.post(
        f"/sites/{site_id}/config-csv",
        files={"file": ("config.csv", csv_text, "text/csv")},
    )
    assert r.status_code == 200
    site = r.json()
    assert site["name"] == "Acme"            # locked
    assert site["domain"] == "acme.example"  # locked
    assert site["brand_voice"] == "New voice"
    assert site["content_type"] == "explainer"


def test_config_csv_download(client):
    site_id = _make_site(client)
    r = client.get(f"/sites/{site_id}/config.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "brand_voice" in r.text
    assert "LOCKED" in r.text


def test_bulk_runs_csv_creates_one_run_per_topic(client, patched_runner):
    site_id = _make_site(client)
    r = client.post(
        f"/sites/{site_id}/runs/csv?auto_approve=true",
        files={"file": ("blogs.csv", MESSY_RUNS_CSV, "text/csv")},
    )
    assert r.status_code == 202
    runs = r.json()
    assert len(runs) == 2
    topics = {run["topic"] for run in client.get(f"/sites/{site_id}/runs").json()}
    assert "Why most enterprise AI pilots fail" in topics


def test_runs_template_download(client):
    site_id = _make_site(client)
    r = client.get(f"/sites/{site_id}/runs/template.csv")
    assert r.status_code == 200
    assert "topic" in r.text.splitlines()[0].lower()
