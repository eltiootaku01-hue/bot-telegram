import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import Chat, GameProfile, MysteryAttempt, MysteryRound, PointTransaction, User
from app.game.mystery import MYSTERY_POINTS, MysteryService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'mystery.db'}")
    await database.create_schema()
    async with database.session() as session:
        session.add_all(
            [
                User(id=7, first_name="Sunna"),
                User(id=8, first_name="Cari"),
                Chat(id=-100, type="supergroup", title="Café Otaku"),
            ]
        )
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_start_round_is_idempotent_per_community_and_day(database):
    service = MysteryService()

    async with database.session(write=True) as session:
        first = await service.start_round(session, chat_id=-100, day_key="2026-09-19")

    async with database.session(write=True) as session:
        second = await service.start_round(session, chat_id=-100, day_key="2026-09-19")

    assert first.created is True
    assert second.created is False
    assert first.round.id == second.round.id
    assert first.case.key == second.case.key


@pytest.mark.asyncio
async def test_correct_answer_awards_points_once_and_locks_round(database):
    service = MysteryService()

    async with database.session(write=True) as session:
        started = await service.start_round(session, chat_id=-100, day_key="2026-09-19")
        round_id = started.round.id
        answer = started.case.answer_index

    async with database.session(write=True) as session:
        result, balance = await service.answer(
            session,
            round_id=round_id,
            user_id=7,
            option_index=answer,
            chat_id=-100,
        )

    assert result == "correct"
    assert balance == MYSTERY_POINTS

    async with database.session(write=True) as session:
        result, balance = await service.answer(
            session,
            round_id=round_id,
            user_id=8,
            option_index=answer,
            chat_id=-100,
        )

    assert result == "already_won"
    assert balance == 0

    async with database.session() as session:
        row = await session.get(MysteryRound, round_id)
        attempts = list(
            await session.scalars(
                select(MysteryAttempt).where(MysteryAttempt.round_id == round_id)
            )
        )
        txs = list(
            await session.scalars(
                select(PointTransaction).where(
                    PointTransaction.chat_id == -100,
                    PointTransaction.reference_type == "mystery",
                    PointTransaction.reference_id == str(round_id),
                )
            )
        )
        profile = await session.scalar(
            select(GameProfile).where(
                GameProfile.user_id == 7,
                GameProfile.chat_id == -100,
            )
        )

    assert row is not None
    assert row.status == "won"
    assert row.winner_user_id == 7
    assert len(attempts) == 1
    assert len(txs) == 1
    assert txs[0].amount == MYSTERY_POINTS
    assert profile is not None
    assert profile.points == MYSTERY_POINTS


@pytest.mark.asyncio
async def test_wrong_answer_consumes_player_attempt(database):
    service = MysteryService()

    async with database.session(write=True) as session:
        started = await service.start_round(session, chat_id=-100, day_key="2026-09-20")

    wrong_index = (started.case.answer_index + 1) % len(started.case.options)

    async with database.session(write=True) as session:
        result, balance = await service.answer(
            session,
            round_id=started.round.id,
            user_id=7,
            option_index=wrong_index,
            chat_id=-100,
        )

    assert result == "wrong"
    assert balance == 0

    async with database.session(write=True) as session:
        result, _ = await service.answer(
            session,
            round_id=started.round.id,
            user_id=7,
            option_index=started.case.answer_index,
            chat_id=-100,
        )

    assert result == "already_answered"


@pytest.mark.asyncio
async def test_different_day_creates_independent_round(database):
    service = MysteryService()

    async with database.session(write=True) as session:
        first = await service.start_round(session, chat_id=-100, day_key="2026-09-19")
        second = await service.start_round(session, chat_id=-100, day_key="2026-09-20")

    assert first.round.id != second.round.id

    async with database.session() as session:
        rows = list(
            await session.scalars(
                select(MysteryRound).where(MysteryRound.chat_id == -100)
            )
        )

    assert len(rows) == 2


@pytest.mark.asyncio
async def test_failed_round_can_be_reactivated_for_publication_retry(database):
    service = MysteryService()

    async with database.session(write=True) as session:
        started = await service.start_round(
            session,
            chat_id=-100,
            day_key="2026-09-21",
        )
        row = await session.get(MysteryRound, started.round.id)
        assert row is not None
        row.status = "failed"
        await session.flush()

    async with database.session(write=True) as session:
        retry = await service.start_round(
            session,
            chat_id=-100,
            day_key="2026-09-21",
        )

    assert retry.created is True
    assert retry.round.id == started.round.id
    assert retry.round.status == "active"
    assert retry.round.message_id is None
