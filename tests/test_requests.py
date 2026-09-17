import asyncio

import pytest

from app.db.database import Database
from app.db.models import Chat, FanRequest, GameProfile, PointTransaction, User
from app.services.requests import RequestService


async def seed_profile(database: Database, *, user_id: int, chat_id: int, points: int) -> None:
    async with database.session() as session:
        session.add(User(id=user_id, username=f"user{user_id}"))
        session.add(Chat(id=chat_id, title=f"chat{chat_id}", type="group"))
        await session.flush()
        session.add(GameProfile(user_id=user_id, chat_id=chat_id, points=points))


async def counts(database: Database, user_id: int, chat_id: int) -> tuple[int, int, int, int]:
    async with database.session() as session:
        request_count = await session.scalar(
            FanRequest.__table__.select()
            .where(FanRequest.user_id == user_id, FanRequest.chat_id == chat_id)
            .count()
        )
        point_count = await session.scalar(
            PointTransaction.__table__.select()
            .where(PointTransaction.user_id == user_id, PointTransaction.chat_id == chat_id)
            .count()
        )
        event_count = await session.scalar(
            FanRequest.__table__.select()
            .where(FanRequest.user_id == user_id, FanRequest.chat_id == chat_id)
            .count()
        )
        profile = await session.scalar(
            GameProfile.__table__.select()
            .where(GameProfile.user_id == user_id, GameProfile.chat_id == chat_id)
        )
        return request_count, point_count, event_count, profile.points


@pytest.mark.asyncio
async def test_create_paid_concurrent_duplicate_source_is_idempotent(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'requests.sqlite3'}")
    await database.create_schema()
    await seed_profile(database, user_id=5, chat_id=50, points=100)

    database_a = Database(f"sqlite+aiosqlite:///{tmp_path / 'requests.sqlite3'}")
    database_b = Database(f"sqlite+aiosqlite:///{tmp_path / 'requests.sqlite3'}")
    service = RequestService()

    async def create(database_for_task: Database):
        async with database_for_task.session(write=True) as session:
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
