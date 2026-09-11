from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import DurableJob


DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_SECONDS = (5, 30, 120, 600, 1800)


class JobQueue:
    """Persistent one-shot jobs with deduplication, recovery and bounded retries."""

    async def enqueue(self, session: AsyncSession, job_type: str, payload: dict, *, dedupe_key: str, run_at: datetime | None = None, commit: bool = True) -> DurableJob:
        job = DurableJob(job_type=job_type, dedupe_key=dedupe_key, payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")), run_at=run_at or utc_now())
        if commit:
            session.add(job)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await session.scalar(select(DurableJob).where(DurableJob.dedupe_key == dedupe_key))
                if existing is None:
                    raise
                return existing
            await session.refresh(job)
            return job
        if not session.in_transaction():
            await session.begin()
        try:
            async with session.begin_nested():
                session.add(job)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(select(DurableJob).where(DurableJob.dedupe_key == dedupe_key))
            if existing is None:
                raise
            return existing
        return job

    async def recover_stale(self, session: AsyncSession, *, job_type: str | None = None, timeout_seconds: int = 300, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> int:
        cutoff = utc_now() - timedelta(seconds=timeout_seconds)
        now = utc_now()
        query = select(DurableJob).where(
            DurableJob.status == "processing",
            ((DurableJob.heartbeat_at.is_not(None) & (DurableJob.heartbeat_at < cutoff)) |
             (DurableJob.heartbeat_at.is_(None) & DurableJob.locked_at.is_not(None) & (DurableJob.locked_at < cutoff))),
        )
        if job_type is not None:
            query = query.where(DurableJob.job_type == job_type)
        jobs = list(await session.scalars(query))
        for job in jobs:
            if job.attempts >= max_attempts:
                job.status = "failed"
                job.last_error = "Job abandoned after maximum recovery attempts"
            else:
                delay = DEFAULT_BACKOFF_SECONDS[min(job.attempts, len(DEFAULT_BACKOFF_SECONDS) - 1)]
                job.status = "pending"
                job.run_at = now + timedelta(seconds=delay)
                job.last_error = "Recovered stale processing job"
            job.locked_at = None
            job.heartbeat_at = None
            job.updated_at = now
        if jobs:
            await session.commit()
        return len(jobs)

    async def claim(self, session: AsyncSession, *, job_type: str | None = None) -> DurableJob | None:
        now = utc_now()
        query = select(DurableJob).where(DurableJob.status == "pending", DurableJob.run_at <= now)
        if job_type is not None:
            query = query.where(DurableJob.job_type == job_type)
        candidate = await session.scalar(query.order_by(DurableJob.id.asc()).limit(1))
        if candidate is None:
            return None
        return await self._claim_id(session, candidate.id, now)

    async def claim_by_dedupe_key(self, session: AsyncSession, dedupe_key: str) -> DurableJob | None:
        """Atomically claim one exact pending job without stealing another job."""
        now = utc_now()
        candidate = await session.scalar(
            select(DurableJob).where(
                DurableJob.dedupe_key == dedupe_key,
                DurableJob.status == "pending",
                DurableJob.run_at <= now,
            )
        )
        if candidate is None:
            return None
        return await self._claim_id(session, candidate.id, now)

    async def _claim_id(self, session: AsyncSession, job_id: int, now: datetime) -> DurableJob | None:
        result = await session.execute(
            update(DurableJob)
            .where(DurableJob.id == job_id, DurableJob.status == "pending")
            .values(
                status="processing",
                attempts=DurableJob.attempts + 1,
                locked_at=now,
                heartbeat_at=now,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            await session.rollback()
            return None
        await session.commit()
        job = await session.get(DurableJob, job_id)
        if job is not None:
            await session.refresh(job)
        return job

    async def renew(self, session: AsyncSession, job_id: int, *, lock_time: datetime) -> bool:
        """Refresh liveness without changing the immutable claim token."""
        now = utc_now()
        result = await session.execute(update(DurableJob).where(DurableJob.id == job_id, DurableJob.status == "processing", DurableJob.locked_at == lock_time).values(heartbeat_at=now, updated_at=now))
        await session.commit()
        return result.rowcount == 1

    async def complete(self, session: AsyncSession, job_id: int, *, lock_time: datetime | None = None) -> bool:
        now = utc_now()
        conditions = [DurableJob.id == job_id, DurableJob.status == "processing"]
        if lock_time is not None:
            conditions.append(DurableJob.locked_at == lock_time)
        result = await session.execute(update(DurableJob).where(*conditions).values(status="completed", completed_at=now, heartbeat_at=None, updated_at=now))
        await session.commit()
        return result.rowcount == 1

    async def fail(self, session: AsyncSession, job_id: int, error: str, *, lock_time: datetime | None = None, retry_at: datetime | None = None, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> bool:
        now = utc_now()
        job = await session.get(DurableJob, job_id)
        if job is None or (lock_time is not None and (job.status != "processing" or job.locked_at != lock_time)):
            return False
        if retry_at is None and job.attempts < max_attempts:
            delay = DEFAULT_BACKOFF_SECONDS[min(job.attempts, len(DEFAULT_BACKOFF_SECONDS) - 1)]
            retry_at = now + timedelta(seconds=delay)
        permanent = job.attempts >= max_attempts and retry_at is None
        conditions = [DurableJob.id == job_id, DurableJob.status == "processing"]
        if lock_time is not None:
            conditions.append(DurableJob.locked_at == lock_time)
        result = await session.execute(update(DurableJob).where(*conditions).values(status="failed" if permanent else "pending", run_at=retry_at or now, locked_at=None, heartbeat_at=None, last_error=error[:4000], updated_at=now))
        await session.commit()
        return result.rowcount == 1
