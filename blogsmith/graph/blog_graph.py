"""The per-blog LangGraph state graph + run/resume orchestration.

Wiring:

    (entry) ─► discovery ─► research ─► outline ─► draft ─► critique ─► gate
                                                                         │
                              approve/auto ──────────────────────────────┤
                                                                         ▼
              (entry on resume) ───────────────────────────────► finalize ─► visuals ─► distribute ─► END
                                                                         ▲
                          gate: pause (await human) ─► END

A conditional entry point lets the SAME graph serve both phases: Phase A starts at
``discovery``; Phase B (resume after email approval) reconstructs state from the
run document and re-enters at ``finalize``. Durability is the Firestore run doc,
so the pause survives a process/Job restart.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from blogsmith.graph import nodes
from blogsmith.graph.context import RunContext, make_config
from blogsmith.graph.state import BlogState
from blogsmith.models import ExpertDecision, RunStatus

logger = logging.getLogger(__name__)

_RESUME_DECISIONS = {ExpertDecision.APPROVE.value, ExpertDecision.EDIT.value}


# Node names are prefixed so they never collide with state-channel keys
# (LangGraph forbids a node and a state key sharing a name).
def _entry_router(state: BlogState) -> str:
    """Phase B if an expert decision is already present, else Phase A."""
    expert = state.get("expert") or {}
    if expert.get("decision") in _RESUME_DECISIONS and state.get("critique"):
        return "do_finalize"
    return "do_discovery"


def _after_gate(state: BlogState) -> str:
    expert = state.get("expert") or {}
    return "do_finalize" if expert.get("decision") == ExpertDecision.APPROVE.value else "wait"


def build_graph():
    g = StateGraph(BlogState)
    g.add_node("do_discovery", nodes.discovery_node)
    g.add_node("do_research", nodes.research_node)
    g.add_node("do_outline", nodes.outline_node)
    g.add_node("do_draft", nodes.draft_node)
    g.add_node("do_critique", nodes.critique_node)
    g.add_node("do_gate", nodes.gate_node)
    g.add_node("do_finalize", nodes.finalize_node)
    g.add_node("do_visuals", nodes.visuals_node)
    g.add_node("do_distribute", nodes.distribute_node)

    g.set_conditional_entry_point(
        _entry_router, {"do_discovery": "do_discovery", "do_finalize": "do_finalize"}
    )
    g.add_edge("do_discovery", "do_research")
    g.add_edge("do_research", "do_outline")
    g.add_edge("do_outline", "do_draft")
    g.add_edge("do_draft", "do_critique")
    g.add_edge("do_critique", "do_gate")
    g.add_conditional_edges("do_gate", _after_gate, {"do_finalize": "do_finalize", "wait": END})
    g.add_edge("do_finalize", "do_visuals")
    g.add_edge("do_visuals", "do_distribute")
    g.add_edge("do_distribute", END)
    return g.compile()


# Compiled once; nodes are stateless (all state flows through config/state).
_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


async def run_pipeline(ctx: RunContext) -> BlogState:
    """Phase A: run from discovery to either the email gate (pause) or completion
    (auto-approve). Returns the final state."""
    initial: BlogState = {
        "topic": ctx.run_input.get("topic"),
        "keyword": ctx.run_input.get("keyword"),
        "status": RunStatus.DISCOVERING.value,
    }
    ctx.set_status(RunStatus.DISCOVERING.value)
    try:
        return await get_graph().ainvoke(initial, make_config(ctx))
    except Exception as exc:  # noqa: BLE001 — record failure on the run
        logger.exception("Pipeline failed for run %s", ctx.run_id)
        ctx.set_status(RunStatus.FAILED.value, error=str(exc))
        raise


async def resume_pipeline(
    ctx: RunContext, state: BlogState, decision: str, edits: str | None = None
) -> BlogState:
    """Phase B: apply the expert decision and run finalize → visuals → distribute.

    ``state`` is rebuilt from the run document (see ``checkpoint.state_from_run``).
    Reject is handled by the caller (no graph run needed).
    """
    expert = {"decision": decision}
    if edits:
        expert["edits"] = edits
    state["expert"] = expert
    ctx.persist("expert", expert, status=RunStatus.FINALIZING)
    try:
        return await get_graph().ainvoke(state, make_config(ctx))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Resume failed for run %s", ctx.run_id)
        ctx.set_status(RunStatus.FAILED.value, error=str(exc))
        raise
