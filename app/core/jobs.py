from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DurableJob


class JobQueue:
    """Persistent one-shot jobs with deduplication and retry state."""

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
    ) -> None:
        now = datetime.utcnow()
        await session.execute(
            update(DurableJob)
            .where(DurableJob.id == job_id)
            .values(
                status="pending" if retry_at else "failed",
                run_at=retry_at or now,
                locked_at=None,
                last_error=error[:4000],
                updated_at=now,
            )
        )
        await session.commit()
