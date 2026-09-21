import asyncio

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import Chat, GameCollection, GameProfile, User, WaifuDetectorDailyUsage, WaifuDetectorRound
from app.core.time import utc_now
from app.game.models import Rarity
from app.game.waifu_detector import MAX_DAILY_DETECTOR_USES, DETECTOR_MOBS, WaifuDetectorService


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'detector.db'}")
    await database.create_schema()
    async with database.session() as session:
        session.add(User(id=7, first_name="Jugador"))
        session.add(Chat(id=-100, type="supergroup", title="Café Otaku"))
        await session.flush()
        profile = GameProfile(user_id=7, chat_id=-100)
        session.add(profile)
        await session.flush()
        session.add(
            GameCollection(
                profile_id=profile.id,
                character_id="anya",
                rarity=Rarity.D.value,
                level=10,
                experience=0,
                copies=1,
                evolution_stage=1,
            )
        )
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_detector_stops_after_three_daily_uses(database):
    service = WaifuDetectorService()

    starts = []
    async with database.session(write=True) as session:
        for _ in range(MAX_DAILY_DETECTOR_USES):
            started = await service.start(
                session,
                user_id=7,
                chat_id=-100,
                day_key="2026-09-21",
                character_id="anya",
            )
            starts.append(started)
        fourth = await service.start(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-21",
            character_id="anya",
        )

    assert all(started is not None for started in starts)
    assert [started.use_number for started in starts] == [1, 2, 3]
    assert fourth is None

    async with database.session() as session:
        usage = await session.scalar(select(WaifuDetectorDailyUsage))
        rounds = list(await session.scalars(select(WaifuDetectorRound)))

    assert usage is not None
    assert usage.uses == 3
    assert len(rounds) == 3


@pytest.mark.asyncio
async def test_detector_round_can_be_resolved_only_once(database):
    service = WaifuDetectorService()

    async with database.session(write=True) as session:
        started = await service.start(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-21",
            character_id="anya",
        )

    assert started is not None

    async with database.session(write=True) as session:
        first = await service.fight(
            session,
            round_id=started.round.id,
            user_id=7,
            chat_id=-100,
        )

    async with database.session(write=True) as session:
        second = await service.fight(
            session,
            round_id=started.round.id,
            user_id=7,
            chat_id=-100,
        )

    assert first[0] in {"won", "lost"}
    assert second[0] == "already_fought"

    async with database.session() as session:
        row = await session.get(WaifuDetectorRound, started.round.id)
        assert row is not None
        assert row.status in {"won", "lost"}


@pytest.mark.asyncio
async def test_detector_concurrent_daily_starts_never_allocate_a_fourth_use(tmp_path):
    database_a = Database(f"sqlite+aiosqlite:///{tmp_path / 'detector-race.db'}")
    database_b = Database(f"sqlite+aiosqlite:///{tmp_path / 'detector-race.db'}")
    await database_a.create_schema()

    async with database_a.session() as session:
        session.add(User(id=8, first_name="Race"))
        session.add(Chat(id=-101, type="supergroup", title="Race"))
        await session.flush()
        profile = GameProfile(user_id=8, chat_id=-101, points=0)
        session.add(profile)
        await session.flush()
        session.add(
            GameCollection(
                profile_id=profile.id,
                character_id="anya",
                rarity=Rarity.D.value,
                level=10,
                experience=0,
                copies=1,
                evolution_stage=1,
            )
        )

    service = WaifuDetectorService()

    async def start(database):
        async with database.session(write=True) as session:
            return await service.start(
                session,
                user_id=8,
                chat_id=-101,
                day_key="2026-09-21",
                character_id="anya",
            )

    results = await asyncio.gather(
        start(database_a),
        start(database_b),
        start(database_a),
        start(database_b),
        start(database_a),
    )

    assert sum(result is not None for result in results) == 3
    assert sum(result is None for result in results) == 2

    async with database_a.session() as session:
        usage = await session.scalar(select(WaifuDetectorDailyUsage))
        rounds = list(await session.scalars(select(WaifuDetectorRound)))

    assert usage is not None
    assert usage.uses == 3
    assert len(rounds) == 3
    assert {round_row.use_number for round_row in rounds} == {1, 2, 3}
    assert DETECTOR_MOBS

    await database_a.close()
    await database_b.close()


@pytest.mark.asyncio
async def test_detector_round_insert_failure_does_not_consume_daily_use(database):
    service = WaifuDetectorService()

    async with database.session(write=True) as session:
        usage = WaifuDetectorDailyUsage(
            user_id=7,
            chat_id=-100,
            day_key="2026-09-22",
            uses=1,
        )
        session.add(usage)
        await session.flush()
        session.add(
            WaifuDetectorRound(
                user_id=7,
                chat_id=-100,
                day_key="2026-09-22",
                use_number=2,
                character_id="anya",
                mob_key=DETECTOR_MOBS[0].key,
                status="active",
                expires_at=utc_now() + timedelta(seconds=120),
            )
        )

    async with database.session(write=True) as session:
        result = await service.start(
            session,
            user_id=7,
            chat_id=-100,
            day_key="2026-09-22",
            character_id="anya",
        )

    assert result is None

    async with database.session() as session:
        usage = await session.scalar(
            select(WaifuDetectorDailyUsage).where(
                WaifuDetectorDailyUsage.user_id == 7,
                WaifuDetectorDailyUsage.chat_id == -100,
                WaifuDetectorDailyUsage.day_key == "2026-09-22",
            )
        )

    assert usage is not None
    assert usage.uses == 1
