from datetime import datetime

import pytest

from app.core.identity import BotIdentity
from app.core.social_turn import SocialTurnArbiter, social_window_key
from app.db.database import Database


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_only_one_bot_wins_the_same_social_turn(database):
    arbiter = SocialTurnArbiter()
    async with database.session() as first_session, database.session() as second_session:
        first = await arbiter.acquire(
            first_session,
            chat_id=123,
            window_key="202609101200",
            identity=BotIdentity.CARI,
        )
        second = await arbiter.acquire(
            second_session,
            chat_id=123,
            window_key="202609101200",
            identity=BotIdentity.CHIE,
        )

        assert first is not None
        assert first.bot_identity == BotIdentity.CARI
        assert second is None
        assert await arbiter.complete(first_session, first)


@pytest.mark.asyncio
async def test_different_chat_or_window_can_have_independent_turns(database):
    arbiter = SocialTurnArbiter()
    async with database.session() as session:
        first = await arbiter.acquire(
            session,
            chat_id=123,
            window_key="202609101200",
            identity=BotIdentity.SUNNA,
        )
        second = await arbiter.acquire(
            session,
            chat_id=456,
            window_key="202609101200",
            identity=BotIdentity.CAMI,
        )

        assert first is not None
        assert second is not None
        assert first.job_id != second.job_id


@pytest.mark.asyncio
async def test_social_window_key_is_minute_deterministic():
    assert social_window_key(datetime(2026, 9, 10, 12, 34, 59)) == "202609101234"
