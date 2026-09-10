from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from app.core.events import EventBus
from app.core.jobs import JobQueue
from app.db.database import Database

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict], Awaitable[None]]
JobHandler = Callable[[dict], Awaitable[None]]


class DurableWorker:
    """Small polling worker that recovers stale work and isolates handler failures."""

    def __init__(
        self,
        database: Database,
        *,
        event_bus: EventBus | None = None,
        job_queue: JobQueue | None = None,
        poll_seconds: float = 1.0,
    ) -> None:
        self.database = database
        self.events = event_bus or EventBus()
        self.jobs = job_queue or JobQueue()
        self.poll_seconds = poll_seconds
        self.event_handlers: dict[str, EventHandler] = {}
        self.job_handlers: dict[str, JobHandler] = {}
        self._stopping = asyncio.Event()

    def register_event(self, event_type: str, handler: EventHandler) -> None:
        if event_type in self.event_handlers:
            raise ValueError(f"Event handler already registered: {event_type}")
        self.event_handlers[event_type] = handler

    def register_job(self, job_type: str, handler: JobHandler) -> None:
        if job_type in self.job_handlers:
            raise ValueError(f"Job handler already registered: {job_type}")
        self.job_handlers[job_type] = handler

    async def run(self) -> None:
        """Run until stop() is called; safe to own from TaskSupervisor."""
        await self._recover()
        while not self._stopping.is_set():
            did_work = await self._process_one_event()
            did_work = (await self._process_one_job()) or did_work
            if not did_work:
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_seconds)
                except TimeoutError:
                    pass

    async def _recover(self) -> None:
        async with self.database.session() as session:
            recovered_events = await self.events.recover_stale(session)
        async with self.database.session() as session:
            recovered_jobs = await self.jobs.recover_stale(session)
        if recovered_events or recovered_jobs:
            logger.warning(
                "Recovered stale work: events=%s jobs=%s", recovered_events, recovered_jobs
            )

    async def _process_one_event(self) -> bool:
        if not self.event_handlers:
            return False
        for event_type in tuple(self.event_handlers):
            async with self.database.session() as session:
                event = await self.events.claim(session, event_type=event_type)
            if event is None:
                continue
            handler = self.event_handlers[event.event_type]
            try:
                await handler(json.loads(event.payload))
            except Exception as exc:
                logger.exception("Event handler failed: %s", event.event_type)
                async with self.database.session() as session:
                    await self.events.fail(session, event.event_id, str(exc))
            else:
                async with self.database.session() as session:
                    await self.events.complete(session, event.event_id)
            return True
        return False

    async def _process_one_job(self) -> bool:
        if not self.job_handlers:
            return False
        for job_type in tuple(self.job_handlers):
            async with self.database.session() as session:
                job = await self.jobs.claim(session, job_type=job_type)
            if job is None:
                continue
            handler = self.job_handlers[job.job_type]
            try:
                await handler(json.loads(job.payload))
            except Exception as exc:
                logger.exception("Job handler failed: %s", job.job_type)
                async with self.database.session() as session:
                    await self.jobs.fail(session, job.id, str(exc))
            else:
                async with self.database.session() as session:
                    await self.jobs.complete(session, job.id)
            return True
        return False

    def stop(self) -> None:
        self._stopping.set()
