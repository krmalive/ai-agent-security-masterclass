from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TraceEvent(BaseModel):
    sequence: int
    run_id: str
    type: str
    message: str
    agent: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Endpoint(BaseModel):
    method: str
    path: str
    authentication: str
    notes: str


class ApplicationSurface(BaseModel):
    application: str
    architecture: list[str]
    features: list[str]
    trust_boundaries: list[str]
    endpoints: list[Endpoint]
    data_assets: list[str]
    risk_hypotheses: list[str]
    constraints: list[str]


class Citation(BaseModel):
    scenario_id: str
    title: str
    pages: str
    excerpt: str


class PlannedTest(BaseModel):
    scenario_id: str
    title: str
    day: int
    priority: str
    estimated_hours: float
    application_feature: str
    risk_hypothesis: str
    rationale: str
    production_safe_procedure: list[str]
    expected_evidence: list[str]
    dependencies: list[str] = Field(default_factory=list)
    citation: Citation | None = None


class RejectedCandidate(BaseModel):
    scenario_id: str
    title: str
    reason: str


class CoverageItem(BaseModel):
    category: str
    status: str
    test_ids: list[str] = Field(default_factory=list)
    note: str


class TestingPlan(BaseModel):
    title: str
    executive_summary: str
    requested_objective: str = ""
    scope_and_constraints: list[str]
    attack_surface: list[str]
    tests: list[PlannedTest]
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list)
    coverage: list[CoverageItem]
    residual_gaps: list[str]
    assumptions: list[str]
    total_hours: float


class RunRecord(BaseModel):
    id: str
    state: RunState = RunState.QUEUED
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    report: TestingPlan | None = None
    events: list[TraceEvent] = Field(default_factory=list, exclude=True)


class StartRunRequest(BaseModel):
    objective: str = Field(
        default=(
            "Build a prioritized, production-safe, three-day security testing plan "
            "for ShopFast using the OWASP Web Security Testing Guide v4.2."
        ),
        min_length=20,
        max_length=4000,
    )
