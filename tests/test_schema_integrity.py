import pytest
from sqlalchemy.exc import IntegrityError

from app.db.database import Database
from app.db.models import (
    GameCollection,
    GameDailyMissionProgress,
    GameProfile,
    PointTransaction,
    User,
    Chat,
    WaifuDetectorDailyUsage,
)


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as session:
        session.add(User(id=7, first_name="Test"))
        session.add(Chat(id=-100, type="supergroup", title="Community"))
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_database_rejects_negative_game_profile_state(database):
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            session.add(
                GameProfile(
                    user_id=7,
                    chat_id=-100,
                    level=0,
                    experience=0,
                    points=0,
                    coins=0,
                    gacha_d_streak=0,
                )
            )


@pytest.mark.asyncio
async def test_database_rejects_invalid_collection_state(database):
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            profile = GameProfile(user_id=7, chat_id=-100)
            session.add(profile)
            await session.flush()
            session.add(
                GameCollection(
                    profile_id=profile.id,
                    character_id="taiga",
                    rarity="D",
                    level=1,
                    copies=0,
                    experience=0,
                    evolution_stage=1,
                )
            )


@pytest.mark.asyncio
async def test_database_rejects_zero_point_ledger_entries(database):
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            session.add(
                PointTransaction(
                    user_id=7,
                    chat_id=-100,
                    amount=0,
                    reason="invalid",
                )
            )


@pytest.mark.asyncio
async def test_database_rejects_detector_usage_above_daily_limit(database):
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            session.add(
                WaifuDetectorDailyUsage(
                    user_id=7,
                    chat_id=-100,
                    day_key="2026-09-21",
                    uses=4,
                )
            )


@pytest.mark.asyncio
async def test_database_rejects_non_positive_daily_mission_target(database):
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            session.add(
                GameDailyMissionProgress(
                    user_id=7,
                    chat_id=-100,
                    day_key="2026-09-21",
                    mission_key="capture",
                    progress=0,
                    target=0,
                )
            )


@pytest.mark.asyncio
async def test_existing_sqlite_schema_gets_invariant_triggers_on_restart(tmp_path):
    path = tmp_path / "schema.db"
    first = Database(f"sqlite+aiosqlite:///{path}")
    await first.create_schema()
    await first.close()

    second = Database(f"sqlite+aiosqlite:///{path}")
    await second.create_schema()

    async with second.session() as session:
        session.add(User(id=8, first_name="Existing"))
        session.add(Chat(id=-101, type="supergroup", title="Existing"))
    with pytest.raises(IntegrityError):
        async with second.session() as session:
            session.add(
                GameProfile(
                    user_id=8,
                    chat_id=-101,
                    level=1,
                    experience=0,
                    points=-1,
                    coins=0,
                    gacha_d_streak=0,
                )
            )

    await second.close()
