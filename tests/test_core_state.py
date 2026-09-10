import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.events import EventBus
from app.core.jobs import JobQueue
from app.db.models import Base


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest.mark.asyncio
async def test_event_publish_is_idempotent(session):
    bus = EventBus()
    first = await bus.publish(session, "waifu.captured", {"user_id": 7}, event_id="evt-1")
    second = await bus.publish(session, "waifu.captured", {"user_id": 7}, event_id="evt-1")

    assert first.event_id == second.event_id == "evt-1"
    event = await bus.claim(session)
    assert event is not None
    assert event.attempts == 1


@pytest.mark.asyncio
async def test_job_enqueue_is_idempotent(session):
    queue = JobQueue()
    first = await queue.enqueue(
        session,
        "telegram.publish",
        {"chat_id": 10},
        dedupe_key="publish:10:asset:5",
    )
    second = await queue.enqueue(
        session,
        "telegram.publish",
        {"chat_id": 10},
        dedupe_key="publish:10:asset:5",
    )

    assert first.id == second.id
    job = await queue.claim(session)
    assert job is not None
    assert job.attempts == 1
