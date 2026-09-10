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
async def test_point_spending_is_atomic_and_never_goes_negative(session):
    repo = MemberRepository()
    await repo.add_points(
        session,
        user_id=7,
        chat_id=-100,
        amount=50,
        reason="seed",
    )

    first = await repo.spend_points(
        session,
        user_id=7,
        chat_id=-100,
        amount=50,
        reason="purchase-1",
    )
    second = await repo.spend_points(
        session,
        user_id=7,
        chat_id=-100,
        amount=50,
        reason="purchase-2",
    )

    assert first == 0
    assert second is None
    profile = await session.scalar(
        select(GameProfile).where(GameProfile.user_id == 7, GameProfile.chat_id == -100)
    )
    assert profile is not None
    assert profile.points == 0
    ledger = list(await session.scalars(
        select(PointTransaction)
        .where(PointTransaction.user_id == 7, PointTransaction.chat_id == -100)
        .order_by(PointTransaction.id)
    ))
    assert [entry.amount for entry in ledger] == [50, -50]
