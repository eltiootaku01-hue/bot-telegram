from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DurableJob


DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_SECONDS = (5, 30, 120, 600, 1800)


class JobQueue:
    """Persistent one-shot jobs with deduplication, recovery and bounded retries."""

    async def enqueue(
        self,
        session: AsyncSession,
        job_type: str,
        payload: dict,
        *,
        dedupe_key: str,
        run_at: datetime | None = None,
    ) -> DurableJob:
        job = DurableJob(
            job_type=job_type,
            dedupe_key=dedupe_key,
            payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            run_at=run_at or datetime.utcnow(),
        )
        session.add(job)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(DurableJob).where(DurableJob.dedupe_key == dedupe_key)
            )
            if existing is None:
                raise
            return existing
        await session.refresh(job)
        return job

    async def recover_stale(
        self,
        session: AsyncSession,
        *,
        job_type: str | None = None,
        timeout_seconds: int = 300,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> int:
        """Return abandoned processing jobs to the queue or permanently fail them."""
        cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        now = datetime.utcnow()
        query = select(DurableJob).where(
            DurableJob.status == "processing",
            DurableJob.locked_at.is_not(None),
            DurableJob.locked_at < cutoff,
        )
        if job_type is not None:
            query = query.where(DurableJob.job_type == job_type)
        result = await session.scalars(query)
        jobs = list(result)
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
            job.updated_at = now
        if jobs:
            await session.commit()
        return len(jobs)

    async def claim(self, session: AsyncSession, *, job_type: str | None = None) -> DurableJob | None:
        now = datetime.utcnow()
        query = select(DurableJob).where(
            DurableJob.status == "pending",
            DurableJob.run_at <= now,
        )
        if job_type is not None:
            query = query.where(DurableJob.job_type == job_type)
        candidate = await session.scalar(query.order_by(DurableJob.id.asc()).limit(1))
        if candidate is None:
            return None

        result = await session.execute(
            update(DurableJob)
            .where(DurableJob.id == candidate.id, DurableJob.status == "pending")
            .values(
                status="processing",
                attempts=DurableJob.attempts + 1,
                locked_at=now,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            await session.rollback()
            return None
        await session.commit()
        await session.refresh(candidate)
        return candidate

    async def complete(self, session: AsyncSession, job_id: int) -> None:
        now = datetime.utcnow()
        await session.execute(
            update(DurableJob)
            .where(DurableJob.id == job_id)
            .values(status="completed", completed_at=now, updated_at=now)
        )
        await session.commit()

    async def fail(
        self,
        session: AsyncSession,
        job_id: int,
        error: str,
        *,
        retry_at: datetime | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        now = datetime.utcnow()
        job = await session.get(DurableJob, job_id)
        if job is None:
            return
        if retry_at is None and job.attempts < max_attempts:
            delay = DEFAULT_BACKOFF_SECONDS[min(job.attempts, len(DEFAULT_BACKOFF_SECONDS) - 1)]
            retry_at = now + timedelta(seconds=delay)
        permanent = job.attempts >= max_attempts and retry_at is None
        await session.execute(
            update(DurableJob)
            .where(DurableJob.id == job_id)
            .values(
                status="failed" if permanent else "pending",
                run_at=retry_at or now,
                locked_at=None,
                last_error=error[:4000],
                updated_at=now,
            )
        )
        await session.commit()
