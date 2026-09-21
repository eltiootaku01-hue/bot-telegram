import asyncio
from datetime import timedelta

import pytest

from app.core.config import Settings
from app.core.time import utc_now
from app.db.database import Database
from app.db.world_models import GameWorldEvent
from app.world.models import PresenterKind, WorldPresenterRef
from app.world.presenter import WorldPresenter
from app.world.runtime import WorldRuntime
from app.world.service import WorldEventService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'world-runtime.db'}")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_runtime_presents_and_completes_authorized_event(database):
    sent: list[tuple[str, int, str]] = []

    async def send(presenter_key: str, chat_id: int, text: str) -> int:
        sent.append((presenter_key, chat_id, text))
        return 501

    runtime = WorldRuntime(
        database,
        WorldPresenter(send),
        settings=Settings(authorized_chat_ids="-100"),
        poll_seconds=0.01,
    )
    service = WorldEventService()

    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            title="Noticias",
            text="Una noticia",
            dedupe_key="runtime-authorized",
        )
        await session.commit()
        event_id = event.id

    assert await runtime.tick() is True
    assert sent == [("sunna", -100, "Noticias

Una noticia")]

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == "published"
    assert event.message_id == 501


@pytest.mark.asyncio
async def test_runtime_cancels_event_when_chat_is_not_authorized(database):
    async def send(_presenter_key: str, _chat_id: int, _text: str) -> int:
        raise AssertionError("unauthorized world event must never reach presenter")

    runtime = WorldRuntime(
        database,
        WorldPresenter(send),
        settings=Settings(authorized_chat_ids="-100"),
    )
    service = WorldEventService()

    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-999,
            presenter=WorldPresenterRef("world", PresenterKind.WORLD_BOT),
            title="Bloqueado",
            text="No enviar",
            dedupe_key="runtime-unauthorized",
        )
        await session.commit()
        event_id = event.id

    assert await runtime.tick() is True

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == "cancelled"


@pytest.mark.asyncio
async def test_runtime_heartbeat_keeps_long_presentation_alive(database):
    send_started = asyncio.Event()
    release = asyncio.Event()
    renewals = 0

    async def send(_presenter_key: str, _chat_id: int, _text: str) -> int:
        send_started.set()
        await release.wait()
        return 777

    runtime = WorldRuntime(
        database,
        WorldPresenter(send),
        settings=Settings(authorized_chat_ids="-100"),
        stale_timeout_seconds=3,
    )
    runtime.heartbeat_seconds = 0.01
    service = WorldEventService()

    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("sunna", PresenterKind.EXISTING_BOT),
            title="Larga",
            text="Presentación lenta",
            dedupe_key="runtime-heartbeat",
            run_at=utc_now(),
        )
        await session.commit()
        event_id = event.id

    original_renew = runtime.events.renew

    async def counted_renew(session, *, event_id: int, lock_time):
        nonlocal renewals
        result = await original_renew(session, event_id=event_id, lock_time=lock_time)
        renewals += int(result)
        return result

    runtime.events.renew = counted_renew

    task = asyncio.create_task(runtime.tick())
    await send_started.wait()
    await asyncio.sleep(0.05)
    assert renewals > 0

    release.set()
    assert await task is True

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == "published"


@pytest.mark.asyncio
async def test_runtime_marks_failed_presentation_as_delivery_unknown(database):
    async def send(_presenter_key: str, _chat_id: int, _text: str) -> int:
        raise RuntimeError("telegram unavailable")

    runtime = WorldRuntime(
        database,
        WorldPresenter(send),
        settings=Settings(authorized_chat_ids="-100"),
    )
    service = WorldEventService()

    async with database.session() as session:
        event = await service.schedule_game_news(
            session,
            chat_id=-100,
            presenter=WorldPresenterRef("cami", PresenterKind.EXISTING_BOT),
            title="Falla",
            text="Test",
            dedupe_key="runtime-delivery-unknown",
        )
        await session.commit()
        event_id = event.id

    assert await runtime.tick() is True

    async with database.session() as session:
        event = await session.get(GameWorldEvent, event_id)

    assert event is not None
    assert event.status == "delivery_unknown"
    assert event.last_error == "telegram unavailable"
