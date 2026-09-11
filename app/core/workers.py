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
        lease_seconds: int = 300,
    ) -> None:
        self.database = database
        self.events = event_bus or EventBus()
        self.jobs = job_queue or JobQueue()
        self.poll_seconds = poll_seconds
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = max(5.0, min(60.0, lease_seconds / 3))
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
        for event_type in tuple(self.event_handlers):
            async with self.database.session() as session:
                recovered = await self.events.recover_stale(session, event_type=event_type, timeout_seconds=self.lease_seconds)
            if recovered:
                logger.warning("Recovered stale events: type=%s count=%s", event_type, recovered)
        for job_type in tuple(self.job_handlers):
            async with self.database.session() as session:
                recovered = await self.jobs.recover_stale(session, job_type=job_type, timeout_seconds=self.lease_seconds)
            if recovered:
                logger.warning("Recovered stale jobs: type=%s count=%s", job_type, recovered)

    async def _heartbeat_event(self, event_id: str, lock_time) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            try:
                async with self.database.session() as session:
                    renewed = await self.events.renew(session, event_id, lock_time=lock_time)
            except Exception:
                logger.exception("Event heartbeat failed; will retry: %s", event_id)
                continue
            if not renewed:
                logger.warning("Event lease lost during heartbeat: %s", event_id)
                return

    async def _heartbeat_job(self, job_id: int, lock_time) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            try:
                async with self.database.session() as session:
                    renewed = await self.jobs.renew(session, job_id, lock_time=lock_time)
            except Exception:
                logger.exception("Job heartbeat failed; will retry: %s", job_id)
                continue
            if not renewed:
                logger.warning("Job lease lost during heartbeat: %s", job_id)
                return

    async def _process_one_event(self) -> bool:
        if not self.event_handlers:
            return False
        for event_type in tuple(self.event_handlers):
            async with self.database.session() as session:
                event = await self.events.claim(session, event_type=event_type)
            if event is None:
                continue
            lock_time = event.locked_at
            handler = self.event_handlers[event.event_type]
            heartbeat = asyncio.create_task(self._heartbeat_event(event.event_id, lock_time))
            try:
                await handler(json.loads(event.payload))
            except Exception as exc:
                logger.exception("Event handler failed: %s", event.event_type)
                async with self.database.session() as session:
                    changed = await self.events.fail(session, event.event_id, str(exc), lock_time=lock_time)
                if not changed:
                    logger.warning("Event lease lost before failure update: %s", event.event_id)
            else:
                async with self.database.session() as session:
                    changed = await self.events.complete(session, event.event_id, lock_time=lock_time)
                if not changed:
                    logger.warning("Event lease lost before completion: %s", event.event_id)
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass
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
            lock_time = job.locked_at
            handler = self.job_handlers[job.job_type]
            heartbeat = asyncio.create_task(self._heartbeat_job(job.id, lock_time))
            try:
                await handler(json.loads(job.payload))
            except Exception as exc:
                logger.exception("Job handler failed: %s", job.job_type)
                async with self.database.session() as session:
                    changed = await self.jobs.fail(session, job.id, str(exc), lock_time=lock_time)
                if not changed:
                    logger.warning("Job lease lost before failure update: %s", job.id)
            else:
                async with self.database.session() as session:
                    changed = await self.jobs.complete(session, job.id, lock_time=lock_time)
                if not changed:
                    logger.warning("Job lease lost before completion: %s", job.id)
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass
            return True
        return False

    def stop(self) -> None:
        self._stopping.set()
