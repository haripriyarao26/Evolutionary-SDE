from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from evolutionary_sde.graph.interviewer import GraphState, run_interviewer_step
from evolutionary_sde.models import (
    CostBenefitRequest,
    DraftEntry,
    SessionCreate,
    SessionState,
    SubmitCodeBody,
)
from evolutionary_sde.services.cost_benefit import analyze_cost_benefit
from evolutionary_sde.storage import JsonStore

DATA_DIR = Path(os.environ.get("EVOLUTIONARY_SDE_DATA", "data")).resolve()
store = JsonStore(DATA_DIR)

app = FastAPI(
    title="Evolutionary-SDE API",
    description="Stateful mock interviewer, draft / decision log, and founder-style cost-benefit scoring.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_graph(session: SessionState) -> GraphState:
    return {
        "problem_statement": session.problem_statement,
        "code": session.latest_code,
        "phase": session.phase,  # type: ignore[assignment]
        "last_interviewer_message": session.last_interviewer_message or "",
        "assess_passed": session.assess_passed if session.assess_passed is not None else False,
        "transcript": [],
    }


def _merge_graph_into_session(session: SessionState, gs: GraphState) -> None:
    session.phase = gs.get("phase", session.phase)  # type: ignore[assignment]
    session.latest_code = gs.get("code", session.latest_code)
    if "assess_passed" in gs:
        session.assess_passed = bool(gs.get("assess_passed"))
    last = gs.get("last_interviewer_message") or ""
    if last:
        session.last_interviewer_message = last
    for row in gs.get("transcript") or []:
        session.history.append({"kind": "transcript_row", "row": row, "phase": row.get("phase")})


@app.post("/sessions", response_model=SessionState)
def create_session(body: SessionCreate) -> SessionState:
    return store.create_session(body.problem_statement)


@app.get("/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return s


@app.post("/sessions/{session_id}/code", response_model=SessionState)
def submit_code(session_id: str, body: SubmitCodeBody) -> SessionState:
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    prev = s.latest_code
    s.latest_code = body.code
    if body.notes:
        s.history.append({"kind": "candidate_note", "content": body.notes, "phase": s.phase})
    store.update_session(s)
    if prev and prev != body.code:
        store.append_draft(
            DraftEntry(
                session_id=session_id,
                phase=s.phase,
                before_code=prev,
                after_code=body.code,
                rationale=body.notes or "",
                tags=["auto_code_revision"],
            )
        )
    return s


@app.post("/sessions/{session_id}/advance", response_model=SessionState)
def advance_phase(session_id: str) -> SessionState:
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    gs = _to_graph(s)
    out = run_interviewer_step(gs)
    _merge_graph_into_session(s, out)
    store.update_session(s)
    return s


@app.post("/drafts", response_model=DraftEntry)
def log_draft(entry: DraftEntry) -> DraftEntry:
    store.append_draft(entry)
    return entry


@app.get("/sessions/{session_id}/decision-log")
def decision_log(session_id: str) -> dict:
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    drafts = store.list_drafts(session_id)
    return {
        "session": s.model_dump(mode="json"),
        "drafts": [d.model_dump(mode="json") for d in drafts],
        "timeline": s.history,
    }


@app.post("/analyze/cost-benefit")
def cost_benefit(req: CostBenefitRequest):
    return analyze_cost_benefit(req).model_dump(mode="json")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    import uvicorn

    uvicorn.run(
        "evolutionary_sde.api.main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8765")),
        reload=os.environ.get("RELOAD", "").lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    run()
