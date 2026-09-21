from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from app.core.time import utc_now
from app.db.database import Database
from app.db.models import GameEncounter
from app.game.wild_scheduler import WildWaifuScheduler


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_has_active_encounter_retires_stale_active_row(database):
    bot = AsyncMock()
    scheduler = WildWaifuScheduler(bot, database)

    async with database.session() as session:
        session.add(
            GameEncounter(
                id="stale-1",
                chat_id=-100,
                character_id="taiga",
                rarity="D",
                answer="taiga",
                expires_at=utc_now() - timedelta(seconds=1),
                status="active",
            )
        )

    assert await scheduler._has_active_encounter(-100) is False

    async with database.session() as session:
        encounter = await session.get(GameEncounter, "stale-1")

    assert encounter is not None
    assert encounter.status == "expired"


@pytest.mark.asyncio
async def test_expire_does_not_overwrite_captured_encounter(database):
    bot = AsyncMock()
    scheduler = WildWaifuScheduler(bot, database)

    async with database.session() as session:
        session.add(
            GameEncounter(
                id="captured-1",
                chat_id=-100,
                character_id="taiga",
                rarity="D",
                answer="taiga",
                expires_at=utc_now() - timedelta(seconds=1),
                status="captured",
            )
        )

    await scheduler.expire("captured-1", -100, 123)

    async with database.session() as session:
        encounter = await session.get(GameEncounter, "captured-1")

    assert encounter is not None
    assert encounter.status == "captured"
    bot.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_expire_transitions_only_an_expired_active_encounter(database):
    bot = AsyncMock()
    scheduler = WildWaifuScheduler(bot, database)

    async with database.session() as session:
        session.add(
            GameEncounter(
                id="active-1",
                chat_id=-100,
                character_id="taiga",
                rarity="D",
                answer="taiga",
                expires_at=utc_now() - timedelta(seconds=1),
                status="active",
            )
        )

    await scheduler.expire("active-1", -100, 456)

    async with database.session() as session:
        encounter = await session.get(GameEncounter, "active-1")

    assert encounter is not None
    assert encounter.status == "expired"
    bot.edit_message_text.assert_awaited_once_with(
        chat_id=-100,
        message_id=456,
        text="😭 La waifu se fue",
        reply_markup=None,
    )


@pytest.mark.asyncio
async def test_spawn_skips_unauthorized_community(database):
    from app.core.config import Settings

    bot = AsyncMock()
    scheduler = WildWaifuScheduler(
        bot,
        database,
        Settings(authorized_chat_ids="-100123"),
    )

    await scheduler.spawn(-100999)

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_group_ids_returns_only_authorized_configured_communities(database) -> None:
    from app.core.config import Settings
    from app.db.community_models import SetupSession

    async with database.session() as session:
        session.add_all(
            [
                SetupSession(
                    user_id=1,
                    chat_id=-100,
                    bot_identity="chie",
                    status="configured",
                ),
                SetupSession(
                    user_id=2,
                    chat_id=-200,
                    bot_identity="chie",
                    status="configured",
                ),
            ]
        )

    scheduler = WildWaifuScheduler(
        AsyncMock(),
        database,
        Settings(authorized_chat_ids="-100"),
    )

    assert await scheduler._group_ids() == [-100]


@pytest.mark.asyncio
async def test_spawn_persists_world_arrival_instead_of_sending_telegram(database, monkeypatch) -> None:
    from app.core.config import Settings
    from app.db.world_models import GameWorldEvent
    from sqlalchemy import select

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr("app.game.wild_scheduler.asyncio.sleep", no_wait)

    bot = AsyncMock()
    scheduler = WildWaifuScheduler(
        bot,
        database,
        Settings(authorized_chat_ids="-100"),
    )

    await scheduler.spawn(-100)

    async with database.session() as session:
        encounter = await session.scalar(select(GameEncounter))
        event = await session.scalar(select(GameWorldEvent))

    assert encounter is not None
    assert event is not None
    assert event.chat_id == -100
    assert event.event_type == "waifu_arrival"
    assert event.presenter_key == "existing_bot:sunna"
    assert event.status == "pending"
    assert encounter.message_id is None
    assert bot.send_message.assert_not_awaited is not None
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_spawn_rolls_back_encounter_when_world_event_creation_fails(database, monkeypatch) -> None:
    from app.core.config import Settings
    from sqlalchemy import select

    async def fail_schedule(*_args, **_kwargs):
        raise RuntimeError("world event unavailable")

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(
        "app.game.wild_scheduler.WorldEventService.schedule_waifu_arrival",
        fail_schedule,
    )
    monkeypatch.setattr("app.game.wild_scheduler.asyncio.sleep", no_wait)

    scheduler = WildWaifuScheduler(
        AsyncMock(),
        database,
        Settings(authorized_chat_ids="-100"),
    )

    with pytest.raises(RuntimeError, match="world event unavailable"):
        await scheduler.spawn(-100)

    async with database.session() as session:
        encounters = list(await session.scalars(select(GameEncounter)))

    assert encounters == []
