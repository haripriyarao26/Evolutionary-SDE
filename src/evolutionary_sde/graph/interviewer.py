from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from evolutionary_sde.services.assess_heuristics import assess_python

Phase = Literal["assess", "inject_chaos", "scale_up", "system_design", "complete"]


class GraphState(TypedDict, total=False):
    problem_statement: str
    code: str
    phase: Phase
    last_interviewer_message: str
    assess_passed: bool
    transcript: Annotated[list[dict[str, Any]], operator.add]


def _t_row(phase: str, content: str) -> dict[str, Any]:
    return {"role": "interviewer", "content": content, "phase": phase}


def node_assess(state: GraphState) -> GraphState:
    res = assess_python(state.get("code") or "")
    lines = [
        "## Phase 1 — The Signal (Big-O & structures)",
        "",
        f"**Heuristic pass** (not proof): time ~ `{res.big_o_guess}`, space ~ `{res.space_guess}`.",
        "",
    ]
    lines.extend(f"- {b}" for b in res.bullets)
    lines.extend(
        [
            "",
            "**Handoff (say this to the candidate):**",
            'How does this handle **emojis**, **nulls / missing values**, **invalid UTF-8**, '
            "**Unicode normalization** (NFC vs NFD), **grapheme clusters** vs code points, "
            "and **pathological inputs** (e.g. multi-GB strings, all-duplicate keys)?",
        ]
    )
    msg = "\n".join(lines)
    return {
        **state,
        "phase": "inject_chaos",
        "assess_passed": res.passed,
        "last_interviewer_message": msg,
        "transcript": [_t_row("assess", msg)],
    }


def node_inject_chaos(state: GraphState) -> GraphState:
    msg = "\n".join(
        [
            "## Phase 2 — The messy reality (Unicode & correctness)",
            "",
            "- Demand explicit **UTF-8 decode** strategy and **error handling** (replace vs strict).",
            "- Sorting/equality: **locale** vs raw code points; **NFC** if deduping human text.",
            "- Emojis: **ZWJ sequences** and **grapheme** boundaries — `len(str)` is not user-perceived length.",
            "- Nulls: sentinel vs Optional; **schema** for missing fields in batch jobs.",
            "- Security: unbounded reads, **ReDoS**, injection if building queries from strings.",
            "",
            "**Handoff:**",
            "We now have **100 million records**. You have **512 MB RAM** on a single host. **Redesign** "
            "for bounded memory: streaming, external algorithms, batching, compression trade-offs, "
            "and where you would **shard** or **partition**.",
        ]
    )
    return {
        **state,
        "phase": "scale_up",
        "last_interviewer_message": msg,
        "transcript": [_t_row("inject_chaos", msg)],
    }


def node_scale_up(state: GraphState) -> GraphState:
    msg = "\n".join(
        [
            "## Phase 3 — 10M+ scale",
            "",
            "- **Memory:** streaming iterators, chunking, spill-to-disk / external sort, sketches vs exact.",
            "- **Hot keys:** skewed partitions; **backpressure** on downstream consumers.",
            "- **I/O:** pagination cursors, batch APIs, connection pool limits.",
            "- **Horizontal:** partition keys, replication, read vs write scaling, **eventual consistency** costs.",
            "",
            "**Handoff:**",
            "The user waits **30 seconds** for a response. How do we move this to an **asynchronous / "
            "event-driven** flow using **Kafka** or **SQS** (or both)? Cover **ordering**, **duplicates**, "
            "**dead-letter queues**, **observability**, and **failure modes**.",
        ]
    )
    return {
        **state,
        "phase": "system_design",
        "last_interviewer_message": msg,
        "transcript": [_t_row("scale_up", msg)],
    }


def node_system_design(state: GraphState) -> GraphState:
    msg = "\n".join(
        [
            "## Phase 4 — The architect",
            "",
            "- **Kafka:** ordered partition log, replay, consumer groups, compaction trade-offs.",
            "- **SQS:** simple queues, FIFO option, visibility timeout, DLQ — great when log semantics overkill.",
            "- **Processing:** **at-least-once**, **idempotency keys**, outbox pattern, saga vs choreo.",
            "- **State:** Redis for locks / rate limits / cache; avoid **dual writes** without reconciliation.",
            "- **Ops:** metrics, traces, SLOs, **cost** of egress + API operations.",
            "",
            "**Founder probe:**",
            "You chose a primary broker / store. Name a **cheaper or faster-to-ship** alternative and "
            "defend your pick in **one tight paragraph** (team skill, ordering needs, replay, compliance).",
            "",
            "Session phase is now **complete** — capture your **decision log** entry via the drafts API.",
        ]
    )
    return {
        **state,
        "phase": "complete",
        "last_interviewer_message": msg,
        "transcript": [_t_row("system_design", msg)],
    }


_STEP_HANDLERS: dict[Phase, Any] = {
    "assess": node_assess,
    "inject_chaos": node_inject_chaos,
    "scale_up": node_scale_up,
    "system_design": node_system_design,
}


def run_interviewer_step(state: GraphState) -> GraphState:
    """Run exactly one layer transition (API / human-in-the-loop)."""
    phase = state.get("phase") or "assess"
    if phase == "complete":
        return state
    fn = _STEP_HANDLERS.get(phase)
    if fn is None:
        return state
    return fn(state)


def build_interviewer_graph() -> StateGraph:
    g = StateGraph(GraphState)
    g.add_node("assess", node_assess)
    g.add_node("inject_chaos", node_inject_chaos)
    g.add_node("scale_up", node_scale_up)
    g.add_node("system_design", node_system_design)
    g.set_entry_point("assess")
    g.add_edge("assess", "inject_chaos")
    g.add_edge("inject_chaos", "scale_up")
    g.add_edge("scale_up", "system_design")
    g.add_edge("system_design", END)
    return g


def compile_interviewer():
    return build_interviewer_graph().compile()
