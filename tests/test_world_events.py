from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.db.database import Database
from app.db.world_models import GameWorldEvent
from app.world.models import (
    PresenterKind,
    WorldEventType,
    WorldPresenterRef,
)
from app.world.service import WorldEventService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'world-events.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_claim_due_claims_exactly_one_event(database):
    service = WorldEventService()
    now = utc_now()

    async with database.session() as session:
        first = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            title="Uno",
            text="Evento uno",
            dedupe_key="event-one",
            run_at=now,
        )
        second = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("cari", PresenterKind.EXISTING_BOT),
            title="Dos",
            text="Evento dos",
            dedupe_key="event-two",
            run_at=now,
        )
        await session.commit()
        first_id = first.id
        second_id = second.id

    async with database.session(write=True) as session:
        claimed = await service.claim_due(session, now=now)

    assert claimed is not None
    assert claimed.event_id == first_id
    assert claimed.lock_time is not None

    async with database.session() as session:
        rows = list(
            await session.scalars(
                select(GameWorldEvent).where(GameWorldEvent.id.in_((first_id, second_id)))
            )
        )

    statuses = {row.id: row.status for row in rows}
    assert statuses[first_id] == "publishing"
    assert statuses[second_id] == "pending"

    async with database.session(write=True) as session:
        second_claim = await service.claim_due(session, now=now)

    assert second_claim is not None
    assert second_claim.event_id == second_id

    async with database.session() as session:
        third_claim = await service.claim_due(session, now=now)

    assert third_claim is None


@pytest.mark.asyncio
async def test_schedule_dedupe_returns_existing_event(database):
    service = WorldEventService()

    async with database.session() as session:
        first = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("world", PresenterKind.WORLD_BOT),
            title="Noticias",
            text="Una noticia",
            dedupe_key="news:2026-09-21",
        )
        await session.commit()

    async with database.session() as session:
        second = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("world", PresenterKind.WORLD_BOT),
            title="Noticias duplicadas",
            text="No debe crear otra fila",
            dedupe_key="news:2026-09-21",
        )

    assert second.id == first.id


@pytest.mark.asyncio
async def test_recover_stale_respects_a_new_heartbeat(database):
    service = WorldEventService()
    claim_time = utc_now() - timedelta(minutes=10)

    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            title="Stale",
            text="Test",
            dedupe_key="stale-event",
        )
        event.status = "publishing"
        event.locked_at = claim_time
        event.heartbeat_at = claim_time
        await session.commit()
        event_id = event.id

    renewal = utc_now()
    async with database.session() as session:
        renewed = await service.renew(
            session,
            event_id=event_id,
            lock_time=claim_time,
        )

    assert renewed is True

    async with database.session(write=True) as session:
        recovered = await service.recover_stale(
            session,
            timeout_seconds=300,
            now=renewal + timedelta(seconds=1),
        )

    assert recovered == 0

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == "publishing"
    assert event.heartbeat_at == renewal or event.heartbeat_at > claim_time


@pytest.mark.asyncio
async def test_claimed_envelope_contains_typed_lease(database):
    service = WorldEventService()

    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("cami", PresenterKind.EXISTING_BOT),
            title="Evento",
            text="Texto",
            dedupe_key="typed-envelope",
        )
        await session.commit()

    async with database.session(write=True) as session:
        envelope = await service.claim_due(session)

    assert envelope is not None
    assert envelope.event_type is WorldEventType.GAME_NEWS
    assert envelope.presenter.key == "cami"
    assert envelope.lock_time is not None


@pytest.mark.asyncio
async def test_claim_due_can_be_scoped_to_one_presenter(database):
    service = WorldEventService()

    async with database.session() as session:
        await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            title="Sunna",
            text="Solo Sunna",
            dedupe_key="presenter-sunna",
        )
        await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("cami", PresenterKind.EXISTING_BOT),
            title="Cami",
            text="Solo Cami",
            dedupe_key="presenter-cami",
        )
        await session.commit()

    async with database.session(write=True) as session:
        claimed = await service.claim_due(
            session,
            presenter_key="existing_bot:sunna",
        )

    assert claimed is not None
    assert claimed.presenter.key == "sunna"

    async with database.session() as session:
        rows = list(
            await session.scalars(
                select(GameWorldEvent).order_by(GameWorldEvent.id.asc())
            )
        )

    assert [row.status for row in rows] == ["publishing", "pending"]
