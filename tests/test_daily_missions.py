import asyncio

import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import (
    Chat,
    GameDailyMissionCredit,
    GameDailyMissionProgress,
    GameProfile,
    PointTransaction,
    User,
)
from app.game.missions import DailyMissionService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'missions.db'}")
    await database.create_schema()
    async with database.session() as session:
        session.add(User(id=7, first_name="Player"))
        session.add(Chat(id=-100, type="supergroup", title="Community"))
        await session.flush()
        session.add(GameProfile(user_id=7, chat_id=-100, points=0))
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_daily_mission_action_reference_counts_once_and_claims_once(database):
    service = DailyMissionService()

    async with database.session(write=True) as session:
        first = await service.record(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-20",
            mission_key="trivia_participation",
            reference_type="trivia_answer",
            reference_id="11:7",
        )
        duplicate = await service.record(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-20",
            mission_key="trivia_participation",
            reference_type="trivia_answer",
            reference_id="11:7",
        )
        second = await service.record(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-20",
            mission_key="trivia_participation",
            reference_type="trivia_answer",
            reference_id="12:7",
        )

        claimed, balance = await service.claim(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-20",
            mission_key="trivia_participation",
        )
        claimed_again, balance_again = await service.claim(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-20",
            mission_key="trivia_participation",
        )

    assert first.progress == 1
    assert duplicate.progress == 1
    assert second.progress == 2
    assert claimed is True
    assert balance == 25
    assert claimed_again is False
    assert balance_again == 0

    async with database.session() as session:
        progress = await session.scalar(select(GameDailyMissionProgress))
        credits = list(await session.scalars(select(GameDailyMissionCredit)))
        transactions = list(
            await session.scalars(
                select(PointTransaction).where(PointTransaction.reference_type == "mission")
            )
        )
        profile = await session.scalar(
            select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
        )

    assert progress is not None
    assert progress.progress == 2
    assert progress.claimed is True
    assert len(credits) == 2
    assert len(transactions) == 1
    assert transactions[0].amount == 25
    assert profile is not None
    assert profile.points == 25


@pytest.mark.asyncio
async def test_daily_mission_progress_accumulates_distinct_concurrent_actions(database):
    service = DailyMissionService()

    async def record(reference_id: str) -> None:
        async with database.session(write=True) as session:
            await service.record(
                session,
                user_id=7,
                chat_id=-100,
                day_key="2026-09-20",
                mission_key="trivia_participation",
                reference_type="trivia_answer",
                reference_id=reference_id,
            )

    await asyncio.gather(record("21:7"), record("22:7"))

    async with database.session() as session:
        progress = await session.scalar(select(GameDailyMissionProgress))

    assert progress is not None
    assert progress.progress == 2
