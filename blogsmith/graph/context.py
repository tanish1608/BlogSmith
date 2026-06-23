"""Per-run execution context.

Carries the live, non-serializable dependencies (model clients, decrypted keys,
site config) that nodes need but must NOT be persisted into the durable state.
Passed at invoke time via ``config["configurable"]["ctx"]`` and pulled by nodes
with :func:`ctx_from_config`.

``persist`` writes a stage slice + status to the run's Firestore document after
each stage — so the API/dashboard show live progress (CleanCrawl's "write metrics
after every page") and the document doubles as the resume checkpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from google.cloud import firestore

from blogsmith.firestore_db import run_doc
from blogsmith.graph.image_model import ImageClient
from blogsmith.graph.model import LlmClient

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    uid: str
    site_id: str
    run_id: str
    site: dict[str, Any]
    run_input: dict[str, Any]
    llm: LlmClient
    images: ImageClient
    auto_approve: bool = False
    persist_enabled: bool = True  # disabled in unit tests that don't touch Firestore
    _stages: dict[str, Any] = field(default_factory=dict)

    # ── Convenience accessors over site config ────────────────────────────────
    @property
    def brand_voice(self) -> str | None:
        return self.site.get("brand_voice")

    def custom_prompt(self, stage: str) -> str | None:
        return (self.site.get("custom_prompts") or {}).get(stage)

    @property
    def image_style(self) -> str | None:
        return self.site.get("image_style")

    @property
    def expert_insights(self) -> str | None:
        return self.run_input.get("expert_insights")

    # ── Persistence ───────────────────────────────────────────────────────────
    def persist(self, stage: str, data: Any, status: str | None = None) -> None:
        """Write a stage slice (and optional status) to the run document."""
        self._stages[stage] = data
        if not self.persist_enabled:
            return
        updates: dict[str, Any] = {
            f"stages.{stage}": data,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if status:
            updates["status"] = status
        try:
            run_doc(self.uid, self.site_id, self.run_id).update(updates)
        except Exception as exc:  # noqa: BLE001 — persistence must not crash the graph
            logger.error("Failed to persist stage %s: %s", stage, exc)

    def update_fields(self, fields: dict[str, Any]) -> None:
        """Write arbitrary top-level fields on the run document (e.g. topic)."""
        if not self.persist_enabled:
            return
        try:
            run_doc(self.uid, self.site_id, self.run_id).update(
                {**fields, "updated_at": firestore.SERVER_TIMESTAMP}
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to update run fields: %s", exc)

    def set_status(self, status: str, error: str | None = None) -> None:
        if not self.persist_enabled:
            return
        updates: dict[str, Any] = {"status": status, "updated_at": firestore.SERVER_TIMESTAMP}
        if error is not None:
            updates["error"] = error
        try:
            run_doc(self.uid, self.site_id, self.run_id).update(updates)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to set status %s: %s", status, exc)


CONFIG_KEY = "ctx"


def ctx_from_config(config: dict | None) -> RunContext:
    if not config or "configurable" not in config or CONFIG_KEY not in config["configurable"]:
        raise RuntimeError("RunContext missing from graph config.")
    return config["configurable"][CONFIG_KEY]


def make_config(ctx: RunContext) -> dict:
    return {"configurable": {CONFIG_KEY: ctx, "thread_id": ctx.run_id}}
