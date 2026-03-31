from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Phase = Literal["assess", "inject_chaos", "scale_up", "system_design", "complete"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionCreate(BaseModel):
    problem_statement: str = Field(..., min_length=1, description="Original problem / prompt")


class SessionState(BaseModel):
    session_id: str
    phase: Phase = "assess"
    problem_statement: str
    latest_code: str = ""
    design_notes: str = ""
    last_interviewer_message: str = ""
    assess_passed: bool | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SubmitCodeBody(BaseModel):
    code: str = Field(..., description="Current solution snapshot")
    notes: str | None = Field(default=None, description="Optional rationale for this revision")


class DraftEntry(BaseModel):
    session_id: str
    phase: Phase
    before_code: str
    after_code: str
    rationale: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class CostBenefitRequest(BaseModel):
    design_summary: str = Field(..., min_length=10)
    primary_choice: str = Field(..., description="e.g. kafka, sqs, redis_streams")
    workload_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional: record_count, qps, regions, retention_days, etc.",
    )
    alternatives: list[str] = Field(
        default_factory=lambda: ["sqs", "kafka", "rabbitmq", "redis_streams"],
        description="Systems to contrast against",
    )


class FounderScore(BaseModel):
    score_1_to_10: int
    summary: str
    cheaper_alternative: str | None = None
    deployment_speed_note: str | None = None
    justify_prompt: str
    risks: list[str] = Field(default_factory=list)
    raw_model: str | None = None
