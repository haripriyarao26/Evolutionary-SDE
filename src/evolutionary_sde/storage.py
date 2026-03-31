from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from evolutionary_sde.models import DraftEntry, SessionState, utcnow


class JsonStore:
    """Tiny file-backed store for sessions and append-only draft log."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._sessions_path = self._dir / "sessions.json"
        self._drafts_path = self._dir / "drafts.jsonl"
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        if self._sessions_path.exists():
            raw = json.loads(self._sessions_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._sessions = raw

    def _persist_sessions(self) -> None:
        self._sessions_path.write_text(
            json.dumps(self._sessions, default=_json_default, indent=2),
            encoding="utf-8",
        )

    def create_session(self, problem_statement: str) -> SessionState:
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, problem_statement=problem_statement)
        with self._lock:
            self._sessions[sid] = state.model_dump(mode="json")
            self._persist_sessions()
        return state

    def get_session(self, session_id: str) -> SessionState | None:
        with self._lock:
            row = self._sessions.get(session_id)
        if not row:
            return None
        return SessionState.model_validate(row)

    def update_session(self, state: SessionState) -> None:
        state.updated_at = utcnow()
        with self._lock:
            self._sessions[state.session_id] = state.model_dump(mode="json")
            self._persist_sessions()

    def append_draft(self, entry: DraftEntry) -> None:
        line = json.dumps(entry.model_dump(mode="json"), default=_json_default)
        with self._lock:
            with self._drafts_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def list_drafts(self, session_id: str) -> list[DraftEntry]:
        if not self._drafts_path.exists():
            return []
        out: list[DraftEntry] = []
        with self._lock:
            text = self._drafts_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("session_id") == session_id:
                out.append(DraftEntry.model_validate(row))
        return out


def _json_default(obj: Any) -> str:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
