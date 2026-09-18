from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.events import EventBus
from app.db.database import Database
from app.db.models import DomainEvent


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_stale_event_recovery_is_fenced_by_heartbeat(database: Database) -> None:
    locked_at = datetime(2020, 1, 1)
    stale_heartbeat = locked_at
    live_heartbeat = locked_at + timedelta(hours=1)
    async with database.sessions() as session:
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

    async with database.sessions() as session:
        event = await session.scalar(select(DomainEvent).where(DomainEvent.event_id == "event-1"))
        assert event is not None

        await session.execute(
            update(DomainEvent)
            .where(DomainEvent.event_id == "event-1")
            .execution_options(synchronize_session=False)
            .values(heartbeat_at=live_heartbeat)
        )

        recovered = await EventBus()._recover_event(
            session,
            event,
            cutoff=stale_heartbeat + timedelta(minutes=5),
            now=live_heartbeat,
            max_attempts=5,
        )
        assert recovered is False
        await session.rollback()

        current = await session.scalar(
            select(DomainEvent).where(DomainEvent.event_id == "event-1")
        )
        assert current is not None
        assert current.status == "processing"
        assert current.heartbeat_at == stale_heartbeat
