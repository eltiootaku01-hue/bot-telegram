import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, GameProfile, PointTransaction
from app.db.repositories import MemberRepository


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
async def test_reference_keyed_reward_is_applied_only_once(session):
    repo = MemberRepository()
    first = await repo.add_points(
        session,
        user_id=7,
        chat_id=-100,
        amount=25,
        reason="capture",
        reference_type="encounter_capture",
        reference_id="enc-1",
    )
    second = await repo.add_points(
        session,
        user_id=7,
        chat_id=-100,
        amount=25,
        reason="capture retry",
        reference_type="encounter_capture",
        reference_id="enc-1",
    )

    assert first == 25
    assert second == 25
    profile = await session.scalar(
        select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
    )
    assert profile is not None
    assert profile.points == 25
    ledger = list(await session.scalars(select(PointTransaction)))
    assert len(ledger) == 1
    assert ledger[0].amount == 25


@pytest.mark.asyncio
async def test_reference_keyed_charge_is_applied_only_once(session):
    repo = MemberRepository()
    await repo.add_points(session, user_id=7, chat_id=-100, amount=50, reason="seed")

    first = await repo.spend_points(
        session,
        user_id=7,
        chat_id=-100,
        amount=30,
        reason="request",
        reference_type="fan_request",
        reference_id="req-1",
    )
    second = await repo.spend_points(
        session,
        user_id=7,
        chat_id=-100,
        amount=30,
        reason="request retry",
        reference_type="fan_request",
        reference_id="req-1",
    )

    assert first == 20
    assert second == 20
    profile = await session.scalar(
        select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
    )
    assert profile is not None
    assert profile.points == 20
    ledger = list(await session.scalars(select(PointTransaction).order_by(PointTransaction.id)))
    assert [entry.amount for entry in ledger] == [50, -30]


@pytest.mark.asyncio
async def test_reference_keyed_charge_is_idempotent_under_concurrency(tmp_path):
    from app.db.database import Database
    from app.db.models import Chat, User

    db_path = tmp_path / "points-concurrent.sqlite3"
    seed_db = Database(f"sqlite+aiosqlite:///{db_path}")
    await seed_db.create_schema()

    async with seed_db.session() as session:
        session.add(User(id=7, first_name="User"))
        session.add(Chat(id=-100, type="supergroup"))
        await session.flush()

        repo = MemberRepository()
        await repo.add_points(
            session,
            user_id=7,
            chat_id=-100,
            amount=50,
            reason="seed",
            commit=False,
        )

    await seed_db.close()
    database_a = Database(f"sqlite+aiosqlite:///{db_path}")
    database_b = Database(f"sqlite+aiosqlite:///{db_path}")
    repo = MemberRepository()

    async def spend(database):
        async with database.session(write=True) as session:
            return await repo.spend_points(
                session,
                user_id=7,
                chat_id=-100,
                amount=30,
                reason="request",
                reference_type="fan_request",
                reference_id="req-concurrent",
                commit=False,
            )

    try:
        first, second = await asyncio.gather(spend(database_a), spend(database_b))
        assert first == 20
        assert second == 20

        async with database_a.session() as session:
            profile = await session.scalar(
                select(GameProfile).where(
                    GameProfile.user_id == 7,
                    GameProfile.chat_id == -100,
                )
            )
            ledger = list(
                await session.scalars(
                    select(PointTransaction).where(
                        PointTransaction.user_id == 7,
                        PointTransaction.chat_id == -100,
                        PointTransaction.reference_type == "fan_request",
                        PointTransaction.reference_id == "req-concurrent",
                    )
                )
            )

        assert profile is not None
        assert profile.points == 20
        assert len(ledger) == 1
        assert ledger[0].amount == -30
    finally:
        await database_b.close()
        await database_a.close()


@pytest.mark.asyncio
async def test_reward_reference_conflict_is_rejected(session):
    repo = MemberRepository()
    first = await repo.add_points(
        session,
        user_id=9,
        chat_id=-101,
        amount=25,
        reason="reward",
        reference_type="mission",
        reference_id="day-1",
    )
    assert first == 25

    with pytest.raises(ValueError, match="different amount"):
        await repo.add_points(
            session,
            user_id=9,
            chat_id=-101,
            amount=50,
            reason="conflict",
            reference_type="mission",
            reference_id="day-1",
        )


@pytest.mark.asyncio
async def test_charge_reference_conflict_is_rejected(session):
    repo = MemberRepository()
    await repo.add_points(session, user_id=10, chat_id=-102, amount=100, reason="seed")

    first = await repo.spend_points(
        session,
        user_id=10,
        chat_id=-102,
        amount=30,
        reason="purchase",
        reference_type="purchase",
        reference_id="one",
    )
    assert first == 70

    with pytest.raises(ValueError, match="different amount"):
        await repo.spend_points(
            session,
            user_id=10,
            chat_id=-102,
            amount=40,
            reason="conflict",
            reference_type="purchase",
            reference_id="one",
        )
