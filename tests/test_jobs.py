from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core.jobs import JobQueue
from app.db.database import Database
from app.db.models import DurableJob


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_stale_job_recovery_is_fenced_by_heartbeat(database: Database) -> None:
    locked_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stale_heartbeat = locked_at
    live_heartbeat = locked_at + timedelta(hours=1)
    async with database.sessions() as session:
        session.add(
            DurableJob(
                job_type="test",
                dedupe_key="job-1",
                status="processing",
                attempts=1,
                locked_at=locked_at,
                heartbeat_at=stale_heartbeat,
            )
        )
        await session.commit()

    async with database.sessions() as session:
        job = await session.scalar(
            select(DurableJob).where(DurableJob.dedupe_key == "job-1")
        )
        assert job is not None

        await session.execute(
            update(DurableJob)
            .where(DurableJob.dedupe_key == "job-1")
            .execution_options(synchronize_session=False)
            .values(heartbeat_at=live_heartbeat)
        )

        recovered = await JobQueue()._recover_job(
            session,
            job,
            cutoff=stale_heartbeat + timedelta(minutes=5),
            now=live_heartbeat,
            max_attempts=5,
        )
        assert recovered is False
        await session.rollback()

        current = await session.scalar(
            select(DurableJob).where(DurableJob.dedupe_key == "job-1")
        )
        assert current is not None
        assert current.status == "processing"
        assert current.heartbeat_at == stale_heartbeat
