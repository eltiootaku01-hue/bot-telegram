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
