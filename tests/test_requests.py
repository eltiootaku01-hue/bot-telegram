import asyncio

import pytest
from sqlalchemy import func, select

from app.db.database import Database
from app.db.models import Chat, DomainEvent, FanRequest, GameProfile, PointTransaction, User
from app.services.requests import DEFAULT_REQUEST_COST, RequestService


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


async def seed_profile(database: Database, *, user_id: int, chat_id: int, points: int) -> None:
    async with database.session() as session:
        session.add(User(id=user_id, first_name="Test"))
        session.add(Chat(id=chat_id, type="supergroup"))
        await session.flush()
        session.add(GameProfile(user_id=user_id, chat_id=chat_id, points=points))


async def counts(database: Database, user_id: int, chat_id: int) -> tuple[int, int, int, int]:
    async with database.session() as session:
        requests = await session.scalar(
            select(func.count(FanRequest.id)).where(
                FanRequest.user_id == user_id,
                FanRequest.chat_id == chat_id,
            )
        )
        charges = await session.scalar(
            select(func.count(PointTransaction.id)).where(
                PointTransaction.user_id == user_id,
                PointTransaction.chat_id == chat_id,
                PointTransaction.reference_type == "fan_request",
            )
        )
        events = await session.scalar(select(func.count(DomainEvent.id)))
        balance = await session.scalar(
            select(GameProfile.points).where(
                GameProfile.user_id == user_id,
                GameProfile.chat_id == chat_id,
            )
        )
    return requests or 0, charges or 0, events or 0, balance or 0


@pytest.mark.asyncio
async def test_create_paid_is_atomic_and_caller_owns_commit(database: Database) -> None:
    await seed_profile(database, user_id=1, chat_id=10, points=100)
    service = RequestService()

    async with database.session() as session:
        result = await service.create_paid(
            session,
            user_id=1,
            chat_id=10,
            description="Una imagen de prueba",
            source_message_id=100,
        )
        assert result is not None
        assert result.created is True
        assert result.remaining_points == 100 - DEFAULT_REQUEST_COST

    assert await counts(database, 1, 10) == (1, 1, 1, 50)


@pytest.mark.asyncio
async def test_create_paid_rolls_back_local_work_when_balance_is_insufficient(database: Database) -> None:
    await seed_profile(database, user_id=2, chat_id=20, points=10)
    service = RequestService()

    async with database.session() as session:
        result = await service.create_paid(
            session,
            user_id=2,
            chat_id=20,
            description="Pedido sin saldo",
            source_message_id=200,
        )
        assert result is None

    assert await counts(database, 2, 20) == (0, 0, 0, 10)


@pytest.mark.asyncio
async def test_create_paid_idempotency_does_not_charge_twice(database: Database) -> None:
    await seed_profile(database, user_id=3, chat_id=30, points=100)
    service = RequestService()

    async with database.session() as session:
        first = await service.create_paid(
            session,
            user_id=3,
            chat_id=30,
            description="Pedido repetible",
            source_message_id=300,
        )
        assert first is not None and first.created is True

    async with database.session() as session:
        second = await service.create_paid(
            session,
            user_id=3,
            chat_id=30,
            description="Pedido repetible",
            source_message_id=300,
        )
        assert second is not None
        assert second.created is False
        assert second.request.id == first.request.id
        assert second.remaining_points == 50

    assert await counts(database, 3, 30) == (1, 1, 1, 50)


@pytest.mark.asyncio
async def test_create_paid_respects_outer_rollback(database: Database) -> None:
    await seed_profile(database, user_id=4, chat_id=40, points=100)
    service = RequestService()

    with pytest.raises(RuntimeError, match="abort outer transaction"):
        async with database.session() as session:
            result = await service.create_paid(
                session,
                user_id=4,
                chat_id=40,
                description="Debe revertirse",
                source_message_id=400,
            )
            assert result is not None
            raise RuntimeError("abort outer transaction")

    assert await counts(database, 4, 40) == (0, 0, 0, 100)


@pytest.mark.asyncio
async def test_create_paid_concurrent_duplicate_source_is_idempotent(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'requests.sqlite3'}")
    await database.create_schema()
    await seed_profile(database, user_id=5, chat_id=50, points=100)

    database_a = Database(f"sqlite+aiosqlite:///{tmp_path / 'requests.sqlite3'}")
    database_b = Database(f"sqlite+aiosqlite:///{tmp_path / 'requests.sqlite3'}")
    service = RequestService()

    async def create(database_for_task: Database):
        async with database_for_task.session() as session:
            return await service.create_paid(
                session,
                user_id=5,
                chat_id=50,
                description="Pedido concurrente",
                source_message_id=500,
            )

    try:
        results = await asyncio.gather(create(database_a), create(database_b))
        assert sorted(result.created for result in results if result is not None) == [False, True]
        assert all(result is not None for result in results)
        assert results[0].request.id == results[1].request.id
        assert await counts(database, 5, 50) == (1, 1, 1, 50)
    finally:
        await database_a.close()
        await database_b.close()
        await database.close()
