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
