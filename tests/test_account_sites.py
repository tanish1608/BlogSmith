"""Account (env key status) + sites CRUD against the local SQLite store."""

from __future__ import annotations


def test_account_reports_env_key_status(client, monkeypatch):
    from blogsmith.config import get_settings

    # No key configured → masked value is None.
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    monkeypatch.setattr(get_settings(), "fallback_gemini_key", None)
    r = client.get("/account")
    assert r.status_code == 200
    assert r.json()["keys"]["gemini_key"] is None

    # Key set in env → masked hint, never plaintext.
    monkeypatch.setattr(get_settings(), "gemini_api_key", "AIzaSECRET12345")
    masked = client.get("/account").json()["keys"]["gemini_key"]
    assert masked == "••••2345"
    assert "SECRET" not in masked


def test_site_crud_roundtrip(client):
    payload = {
        "name": "Acme Compliance Blog",
        "domain": "acme.example",
        "brand_voice": "Direct, no fluff, expert.",
        "custom_prompts": {"draft": "Always cite the DPDPA section number."},
        "pillar_cluster_map": {"data-privacy": ["dpdpa", "consent", "data fiduciary"]},
        "discovery": {"source": "seed", "seed_topics": ["DPDPA compliance checklist"]},
        "schedule": {"enabled": True, "cadence": "daily", "times": ["09:00"], "count_per_run": 3},
    }
    r = client.post("/sites", json=payload)
    assert r.status_code == 201
    site = r.json()
    site_id = site["id"]
    assert site["name"] == "Acme Compliance Blog"
    assert site["custom_prompts"]["draft"].startswith("Always cite")
    assert site["created_at"] is not None

    # List
    r = client.get("/sites")
    assert r.status_code == 200
    assert any(s["id"] == site_id for s in r.json())

    # Patch
    r = client.patch(f"/sites/{site_id}", json={"brand_voice": "Updated voice."})
    assert r.status_code == 200
    assert r.json()["brand_voice"] == "Updated voice."
    assert r.json()["domain"] == "acme.example"  # untouched field preserved

    # Get
    r = client.get(f"/sites/{site_id}")
    assert r.status_code == 200
    assert r.json()["schedule"]["count_per_run"] == 3

    # Delete
    assert client.delete(f"/sites/{site_id}").status_code == 204
    assert client.get(f"/sites/{site_id}").status_code == 404
