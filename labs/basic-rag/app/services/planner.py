from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.crew.factory import SecurityPlanningCrewFactory
from app.domain.models import RunRecord, RunState, TestingPlan
from app.services.runs import RunStore
from app.services.validation import enrich_citations

logger = logging.getLogger(__name__)


class PlannerService:
    def __init__(self, settings: Settings, store: RunStore):
        self.settings = settings
        self.store = store
        self.factory = SecurityPlanningCrewFactory(settings)
        self._active_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    def start(self, objective: str) -> RunRecord:
        errors = self.settings.readiness_errors()
        if errors:
            raise RuntimeError("; ".join(errors))
        record = self.store.create()
        task = asyncio.create_task(self._execute(record.id, objective))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record

    async def _execute(self, run_id: str, objective: str) -> None:
        async with self._active_lock:
            self.store.set_state(run_id, RunState.RUNNING)
            self.store.emit(
                run_id,
                "run_started",
                "Security test plan generation started",
                data={"objective": objective},
            )
            self.store.emit(run_id, "agent_started", "Application Analyst started", agent="Application Analyst")

            def emit(event_type: str, message: str, agent: str | None, data: dict | None) -> None:
                self.store.emit(run_id, event_type, message, agent=agent, data=data)

            try:
                crew = await asyncio.to_thread(self.factory.build, emit)
                result = await asyncio.to_thread(crew.kickoff, inputs={"objective": objective})
                raw_plan = result.pydantic
                if raw_plan is None:
                    raw_plan = TestingPlan.model_validate_json(result.raw)
                plan = enrich_citations(raw_plan, self.settings)
                plan.requested_objective = objective
                for item in plan.coverage:
                    self.store.emit(
                        run_id,
                        "coverage_updated",
                        f"{item.category}: {item.status}",
                        agent="Plan Reviewer",
                        data=item.model_dump(),
                    )
                self.store.set_state(run_id, RunState.COMPLETED, report=plan)
                self.store.emit(
                    run_id,
                    "report_ready",
                    f"Final plan ready: {len(plan.tests)} tests across {plan.total_hours} hours",
                    data={"tests": len(plan.tests), "hours": plan.total_hours},
                )
            except Exception as exc:
                logger.exception("Planning run %s failed", run_id)
                self.store.set_state(run_id, RunState.FAILED, error=str(exc))
                self.store.emit(run_id, "run_failed", str(exc), data={"error_type": type(exc).__name__})
