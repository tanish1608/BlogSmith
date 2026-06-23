"""Firestore-as-checkpoint helpers.

Rather than a custom LangGraph ``BaseCheckpointSaver`` (fragile across library
versions), durability uses the run document itself: every stage persists its
slice, so a run paused at the email gate can be resumed in a fresh process by
rebuilding the graph state from the stored slices. This keeps secrets out of any
checkpoint and gives the API a single source of truth.
"""

from __future__ import annotations

from typing import Any

from blogsmith.graph.state import BlogState

# Slices that, once present, mean a phase has completed.
_RESUMABLE_SLICES = ("discovery", "research", "outline", "draft", "critique")


def state_from_run(run_data: dict[str, Any]) -> BlogState:
    """Rebuild graph state from a stored run document (for Phase-B resume)."""
    stages = run_data.get("stages", {}) or {}
    state: BlogState = {
        "topic": run_data.get("topic"),
        "keyword": run_data.get("keyword"),
    }
    for slice_name in (
        "discovery", "research", "outline", "draft", "critique",
        "expert", "final", "visuals", "distribution",
    ):
        if slice_name in stages:
            state[slice_name] = stages[slice_name]  # type: ignore[literal-required]
    return state


def is_resumable(run_data: dict[str, Any]) -> bool:
    """True if the run has progressed far enough to resume past the gate."""
    stages = run_data.get("stages", {}) or {}
    return "critique" in stages
