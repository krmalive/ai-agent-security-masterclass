from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.domain.models import RunRecord, StartRunRequest, TestingPlan
from app.rag.manifest import build_manifest
from app.services.planner import PlannerService
from app.services.runs import RunStore

router = APIRouter(prefix="/api")


def _services(request: Request) -> tuple[RunStore, PlannerService]:
    return request.app.state.run_store, request.app.state.planner


@router.get("/status")
async def status() -> dict:
    manifest_count = 0
    if settings.wstg_pdf_path.exists():
        manifest_count = len(build_manifest(str(settings.wstg_pdf_path)))
    return {
        "ready": not settings.readiness_errors(),
        "errors": settings.readiness_errors(),
        "framework": "CrewAI 1.15",
        "agents": ["Application Analyst", "WSTG Test Planner", "Plan Reviewer"],
        "wstg_pdf": settings.wstg_pdf_path.name,
        "wstg_scenarios": manifest_count,
        "vector_store": "ChromaDB (persistent)",
        "embedding_model": settings.embedding_model,
        "chat_model": settings.chat_model,
    }


@router.post("/runs", response_model=RunRecord, status_code=202)
async def start_run(body: StartRunRequest, request: Request) -> RunRecord:
    _, planner = _services(request)
    try:
        return planner.start(body.objective.strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: str, request: Request) -> RunRecord:
    store, _ = _services(request)
    run = store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/report", response_model=TestingPlan)
async def get_report(run_id: str, request: Request) -> TestingPlan:
    store, _ = _services(request)
    run = store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.report:
        raise HTTPException(status_code=409, detail=f"Report is not ready; run is {run.state}")
    return run.report


@router.get("/runs/{run_id}/events")
async def events(
    run_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
) -> EventSourceResponse:
    store, _ = _services(request)
    if not store.get(run_id):
        raise HTTPException(status_code=404, detail="Run not found")

    async def generate():
        async for event in store.stream(run_id, after=after):
            yield {
                "id": str(event.sequence),
                "event": event.type,
                "data": json.dumps(event.model_dump(mode="json")),
            }

    return EventSourceResponse(generate(), ping=15)
