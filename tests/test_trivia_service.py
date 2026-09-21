from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.db.database import Database
from app.db.models import Chat, GameProfile, User
from app.db.trivia_models import TriviaAttempt, TriviaRound
from app.game.trivia import TriviaService


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_start_round_retires_expired_active_round(database):
    service = TriviaService()

    async with database.session() as session:
        stale = TriviaRound(
            chat_id=-100,
            question="vieja",
            options='["a", "b"]',
            answer_index=0,
            explanation="",
            points=10,
            status="active",
            expires_at=utc_now() - timedelta(seconds=1),
        )
        session.add(stale)

    async with database.session() as session:
        created = await service.start_round(session, -100)

    assert created is not None
    round_row, _ = created

    async with database.session() as session:
        old_round = await session.get(TriviaRound, stale.id)
        new_round = await session.get(TriviaRound, round_row.id)

    assert old_round is not None
    assert old_round.status == "expired"
    assert new_round is not None
    assert new_round.status == "active"


@pytest.mark.asyncio
async def test_answer_joins_caller_transaction(database):
    service = TriviaService()

    async with database.session() as session:
        session.add(User(id=7, first_name="Test"))
        session.add(Chat(id=-100, type="supergroup", title="Community"))
        await session.flush()
        session.add(GameProfile(user_id=7, chat_id=-100))
        round_row = TriviaRound(
            chat_id=-100,
            question="Pregunta",
            options='["correcta", "incorrecta"]',
            answer_index=0,
            explanation="",
            points=20,
            status="active",
            expires_at=utc_now() + timedelta(seconds=60),
        )
        session.add(round_row)
        await session.commit()
        round_id = round_row.id

    async with database.session() as session:
        result, balance = await service.answer(
            session,
            round_id,
            7,
            0,
            chat_id=-100,
        )
        assert result == "correct"
        assert balance == 20
        await session.rollback()

    async with database.session() as session:
        stored_round = await session.get(TriviaRound, round_id)
        attempts = list(
            await session.scalars(
                select(TriviaAttempt).where(TriviaAttempt.round_id == round_id)
            )
        )
        profile = await session.scalar(
            select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
        )

    assert stored_round is not None
    assert stored_round.status == "active"
    assert attempts == []
    assert profile is not None
    assert profile.points == 0


@pytest.mark.asyncio
async def test_start_round_keeps_existing_live_round(database):
    service = TriviaService()

    async with database.session() as session:
        first = await service.start_round(session, -100)

    async with database.session() as session:
        second = await service.start_round(session, -100)

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_start_round_does_not_duplicate_delivery_unknown_round(database):
    service = TriviaService()

    async with database.session() as session:
        row = TriviaRound(
            chat_id=-100,
            question="ambigua",
            options='["a", "b"]',
            answer_index=0,
            explanation="",
            points=10,
            status="delivery_unknown",
            expires_at=utc_now() + timedelta(seconds=60),
            message_id=None,
        )
        session.add(row)

    async with database.session(write=True) as session:
        created = await service.start_round(session, -100)

    assert created is None

    async with database.session() as session:
        stored = await session.scalar(
            select(TriviaRound).where(
                TriviaRound.chat_id == -100,
                TriviaRound.status == "delivery_unknown",
            )
        )

    assert stored is not None
