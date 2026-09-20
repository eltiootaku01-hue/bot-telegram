from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.db.database import Database
from app.db.models import CafeDailyEventRound
from app.services.cafe_events import CAFE_DAILY_EVENTS, CafeEventService


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


def test_daily_event_is_deterministic_per_day_and_chat() -> None:
    service = CafeEventService()

    first = service.event_for("2026-09-20", -100)
    second = service.event_for("2026-09-20", -100)

    assert first == second
    assert first in CAFE_DAILY_EVENTS


@pytest.mark.asyncio
async def test_start_event_is_idempotent_for_chat_and_day(database: Database) -> None:
    service = CafeEventService()

    async with database.session(write=True) as session:
        first = await service.start_event(session, chat_id=-100, day_key="2026-09-20")
        await session.flush()

    async with database.session(write=True) as session:
        second = await service.start_event(session, chat_id=-100, day_key="2026-09-20")

    assert first.created is True
    assert second.created is False
    assert first.round.id == second.round.id
    assert second.round.event_key == first.event.key


@pytest.mark.asyncio
async def test_start_event_allows_next_day(database: Database) -> None:
    service = CafeEventService()

    async with database.session(write=True) as session:
        first = await service.start_event(session, chat_id=-100, day_key="2026-09-20")
        second = await service.start_event(session, chat_id=-100, day_key="2026-09-21")

    assert first.round.id != second.round.id


@pytest.mark.asyncio
async def test_expire_old_retires_only_stale_active_rows(database: Database) -> None:
    service = CafeEventService()

    async with database.session(write=True) as session:
        stale = CafeDailyEventRound(
            chat_id=-100,
            day_key="2026-09-18",
            event_key="morning-cleanup",
            title="Viejo",
            text="Viejo",
            status="active",
            created_at=utc_now() - timedelta(days=2),
            updated_at=utc_now(),
        )
        fresh = CafeDailyEventRound(
            chat_id=-100,
            day_key="2026-09-20",
            event_key="shared-table",
            title="Actual",
            text="Actual",
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add_all([stale, fresh])

    async with database.session(write=True) as session:
        count = await service.expire_old(session, chat_id=-100)

    assert count == 1

    async with database.session() as session:
        rows = list(
            await session.scalars(
                select(CafeDailyEventRound).where(CafeDailyEventRound.chat_id == -100)
            )
        )

    by_key = {row.day_key: row for row in rows}
    assert by_key["2026-09-18"].status == "expired"
    assert by_key["2026-09-20"].status == "active"


@pytest.mark.asyncio
async def test_mark_published_is_idempotent(database: Database) -> None:
    service = CafeEventService()

    async with database.session(write=True) as session:
        started = await service.start_event(session, chat_id=-100, day_key="2026-09-20")

    async with database.session(write=True) as session:
        first = await service.mark_published(session, round_id=started.round.id, message_id=101)

    async with database.session(write=True) as session:
        second = await service.mark_published(session, round_id=started.round.id, message_id=202)

    assert first is not None
    assert second is not None
    assert second.message_id == 101
    assert second.status == "published"


@pytest.mark.asyncio
async def test_claim_publication_is_single_winner(tmp_path) -> None:
    import asyncio

    database_a = Database(f"sqlite+aiosqlite:///{tmp_path / 'event-race.db'}")
    database_b = Database(f"sqlite+aiosqlite:///{tmp_path / 'event-race.db'}")
    await database_a.create_schema()
    service = CafeEventService()

    async with database_a.session(write=True) as session:
        started = await service.start_event(session, chat_id=-100, day_key="2026-09-20")
        round_id = started.round.id

    async def claim(database):
        async with database.session(write=True) as session:
            return await service.claim_publication(session, round_id=round_id)

    first, second = await asyncio.gather(
        claim(database_a),
        claim(database_b),
    )

    assert sorted((first, second)) == [False, True]

    async with database_a.session() as session:
        row = await session.get(CafeDailyEventRound, round_id)

    assert row is not None
    assert row.status == "publishing"
    await database_a.close()
    await database_b.close()
