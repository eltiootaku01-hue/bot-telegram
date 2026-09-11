from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.core.jobs import JobQueue
from app.core.time import utc_now
from app.db.database import Database
from app.db.models import DomainEvent, DurableJob


@pytest.fixture
async def session():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as db:
        yield db
    await database.close()


@pytest.mark.asyncio
async def test_utc_now_is_utc_and_database_compatible():
    now = utc_now()
    assert now.tzinfo is None
    assert abs((now - utc_now()).total_seconds()) < 1


@pytest.mark.asyncio
async def test_event_publish_is_idempotent(session: AsyncSession):
    bus = EventBus()
    first = await bus.publish(session, "waifu.captured", {"user_id": 7}, event_id="evt-1")
    second = await bus.publish(session, "waifu.captured", {"user_id": 7}, event_id="evt-1")
    assert first.event_id == second.event_id == "evt-1"
    event = await bus.claim(session)
    assert event is not None
    assert event.attempts == 1


@pytest.mark.asyncio
async def test_job_enqueue_is_idempotent(session: AsyncSession):
    queue = JobQueue()
    first = await queue.enqueue(session, "telegram.publish", {"chat_id": 10}, dedupe_key="publish:10:asset:5")
    second = await queue.enqueue(session, "telegram.publish", {"chat_id": 10}, dedupe_key="publish:10:asset:5")
    assert first.id == second.id
    job = await queue.claim(session)
    assert job is not None
    assert job.attempts == 1


@pytest.mark.asyncio
async def test_transactional_event_dedupe_does_not_force_commit(session: AsyncSession):
    bus = EventBus()
    first = await bus.publish(session, "fan_request.created", {"request_id": 9}, event_id="evt-tx-1", commit=False)
    second = await bus.publish(session, "fan_request.created", {"request_id": 9}, event_id="evt-tx-1", commit=False)
    assert first.event_id == second.event_id == "evt-tx-1"
    await session.rollback()
    assert await session.scalar(select(DomainEvent).where(DomainEvent.event_id == "evt-tx-1")) is None


@pytest.mark.asyncio
async def test_transactional_job_dedupe_does_not_force_commit(session: AsyncSession):
    queue = JobQueue()
    first = await queue.enqueue(session, "media.publish", {"asset_id": 9}, dedupe_key="media:9", commit=False)
    second = await queue.enqueue(session, "media.publish", {"asset_id": 9}, dedupe_key="media:9", commit=False)
    assert first.id == second.id
    await session.rollback()
    assert await session.scalar(select(DurableJob).where(DurableJob.dedupe_key == "media:9")) is None


@pytest.mark.asyncio
async def test_job_completion_is_fenced_by_lease(session: AsyncSession):
    queue = JobQueue()
    job = await queue.enqueue(session, "telegram.publish", {"chat_id": 10}, dedupe_key="fenced-job")
    claimed = await queue.claim(session)
    assert claimed is not None
    wrong_lock = claimed.locked_at + timedelta(seconds=1)
    assert await queue.complete(session, job.id, lock_time=wrong_lock) is False
    assert await queue.complete(session, job.id, lock_time=claimed.locked_at) is True
    refreshed = await session.get(DurableJob, job.id)
    assert refreshed is not None
    assert refreshed.status == "completed"


@pytest.mark.asyncio
async def test_job_heartbeat_extends_liveness_without_changing_claim(session: AsyncSession):
    queue = JobQueue()
    job = await queue.enqueue(session, "telegram.publish", {"chat_id": 10}, dedupe_key="heartbeat-job")
    claimed = await queue.claim(session)
    assert claimed is not None
    original_lock = claimed.locked_at
    assert await queue.renew(session, job.id, lock_time=original_lock) is True
    refreshed = await session.get(DurableJob, job.id)
    assert refreshed is not None
    assert refreshed.locked_at == original_lock
    assert refreshed.heartbeat_at is not None
    assert await queue.complete(session, job.id, lock_time=original_lock) is True


@pytest.mark.asyncio
async def test_event_heartbeat_extends_liveness_without_changing_claim(session: AsyncSession):
    bus = EventBus()
    await bus.publish(session, "telegram.publish", {"chat_id": 10}, event_id="heartbeat-event")
    claimed = await bus.claim(session)
    assert claimed is not None
    original_lock = claimed.locked_at
    assert await bus.renew(session, claimed.event_id, lock_time=original_lock) is True
    refreshed = await session.get(DomainEvent, claimed.id)
    assert refreshed is not None
    assert refreshed.locked_at == original_lock
    assert refreshed.heartbeat_at is not None
    assert await bus.complete(session, claimed.event_id, lock_time=original_lock) is True
