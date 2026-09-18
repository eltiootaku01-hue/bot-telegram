from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.events import EventBus
from app.db.models import Base, DomainEvent


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_stale_event_recovery_is_fenced_by_heartbeat(session_factory) -> None:
    locked_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stale_heartbeat = locked_at
    live_heartbeat = locked_at + timedelta(hours=1)
    async with session_factory() as session:
        session.add(
            DomainEvent(
                event_id="event-1",
                event_type="test",
                status="processing",
                attempts=1,
                locked_at=locked_at,
                heartbeat_at=stale_heartbeat,
            )
        )
        await session.commit()

    async with session_factory() as recovery_session, session_factory() as heartbeat_session:
        event = await recovery_session.scalar(select(DomainEvent).where(DomainEvent.event_id == "event-1"))
        assert event is not None

        await heartbeat_session.execute(
            update(DomainEvent)
            .where(DomainEvent.event_id == "event-1")
            .values(heartbeat_at=live_heartbeat)
        )
        await heartbeat_session.commit()

        recovered = await EventBus()._recover_event(
            recovery_session,
            event,
            cutoff=stale_heartbeat + timedelta(minutes=5),
            now=live_heartbeat,
            max_attempts=5,
        )
        assert recovered is False
        await recovery_session.rollback()

        current = await heartbeat_session.scalar(
            select(DomainEvent).where(DomainEvent.event_id == "event-1")
        )
        assert current is not None
        assert current.status == "processing"
        assert current.heartbeat_at == live_heartbeat
