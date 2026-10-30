from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.models import RunRecord, RunState, TestingPlan, TraceEvent


class RunStore:
    """Thread-safe, in-memory run state with replayable live event streams."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._subscribers: dict[str, set[asyncio.Queue[TraceEvent]]] = {}
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def create(self) -> RunRecord:
        record = RunRecord(id=uuid4().hex)
        with self._lock:
            self._runs[record.id] = record
            self._subscribers[record.id] = set()
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def set_state(
        self,
        run_id: str,
        state: RunState,
        *,
        report: TestingPlan | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.state = state
            if state == RunState.RUNNING:
                run.started_at = datetime.now(timezone.utc)
            if state in (RunState.COMPLETED, RunState.FAILED):
                run.completed_at = datetime.now(timezone.utc)
            run.report = report or run.report
            run.error = error

    def emit(
        self,
        run_id: str,
        event_type: str,
        message: str,
        *,
        agent: str | None = None,
        data: dict | None = None,
    ) -> TraceEvent:
        with self._lock:
            run = self._runs[run_id]
            event = TraceEvent(
                sequence=len(run.events) + 1,
                run_id=run_id,
                type=event_type,
                message=message,
                agent=agent,
                data=data or {},
            )
            run.events.append(event)
            queues = tuple(self._subscribers[run_id])
        if self._loop and self._loop.is_running():
            for queue in queues:
                self._loop.call_soon_threadsafe(queue.put_nowait, event)
        return event

    async def stream(self, run_id: str, after: int = 0) -> AsyncIterator[TraceEvent]:
        queue: asyncio.Queue[TraceEvent] = asyncio.Queue()
        with self._lock:
            run = self._runs[run_id]
            backlog = [event for event in run.events if event.sequence > after]
            self._subscribers[run_id].add(queue)
        try:
            for event in backlog:
                yield event
            while True:
                run = self.get(run_id)
                terminal_event_seen = bool(
                    run
                    and run.events
                    and run.events[-1].type in ("report_ready", "run_failed")
                )
                if run and run.state in (RunState.COMPLETED, RunState.FAILED) and terminal_event_seen and queue.empty():
                    break
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    continue
        finally:
            with self._lock:
                self._subscribers.get(run_id, set()).discard(queue)


run_store = RunStore()
