import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, GameCollection, GameProfile
from app.game.progression import apply_capture_progression


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest.mark.asyncio
async def test_capture_progression_keeps_copies_and_xp_across_repeated_captures(session):
    profile = GameProfile(user_id=7, chat_id=-100)
    session.add(profile)
    await session.flush()

    first_collection, first = await apply_capture_progression(
        session,
        profile_id=profile.id,
        character_id="anya",
        rarity="D",
    )
    await session.commit()

    second_collection, second = await apply_capture_progression(
        session,
        profile_id=profile.id,
        character_id="anya",
        rarity="D",
    )
    await session.commit()

    assert first.points_gained == 10
    assert second.points_gained == 10
    assert first_collection.copies == 1
    assert second_collection.copies == 2
    assert second_collection.experience == 65

    refreshed = await session.scalar(select(GameProfile).where(GameProfile.id == profile.id))
    assert refreshed is not None
    assert refreshed.experience == 65

    rows = list(await session.scalars(select(GameCollection)))
    assert len(rows) == 1
    assert rows[0].copies == 2
