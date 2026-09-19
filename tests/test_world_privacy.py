import pytest
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldUsageStat
from app.services.world import WorldService


@pytest.mark.asyncio
async def test_clear_user_statistics_preserves_world_aggregates() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    service = WorldService()

    async with database.session() as session:
        await service.observe(
            session,
            bot_identity=BotIdentity.SUNNA,
            entry_type="action",
            entry_key="gacha",
            scope_type="user",
            scope_id="42",
        )
        await service.observe(
            session,
            bot_identity=BotIdentity.SUNNA,
            entry_type="action",
            entry_key="gacha",
            scope_type="user_chat",
            scope_id="42:-100",
        )
        await service.observe(
            session,
            bot_identity=BotIdentity.SUNNA,
            entry_type="action",
            entry_key="gacha",
            scope_type="world",
            scope_id="global",
            delta=3,
        )

        deleted = await service.clear_user_statistics(session, user_id=42)
        assert deleted == 2

    async with database.session() as session:
        rows = list(await session.scalars(select(WorldUsageStat)))

    assert len(rows) == 1
    assert rows[0].scope_type == "world"
    assert rows[0].count == 3
    await database.close()


@pytest.mark.asyncio
async def test_clear_user_statistics_can_be_scoped_to_one_chat_and_identity() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    service = WorldService()

    async with database.session() as session:
        await service.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="intent",
            entry_key="greeting",
            scope_type="user_chat",
            scope_id="42:-100",
        )
        await service.observe(
            session,
            bot_identity=BotIdentity.SUNNA,
            entry_type="action",
            entry_key="gacha",
            scope_type="user_chat",
            scope_id="42:-100",
        )
        await service.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="intent",
            entry_key="greeting",
            scope_type="user_chat",
            scope_id="42:-200",
        )

        deleted = await service.clear_user_statistics(
            session,
            user_id=42,
            bot_identity=BotIdentity.SUNNA,
            chat_id=-100,
        )
        assert deleted == 1

    async with database.session() as session:
        rows = list(await session.scalars(select(WorldUsageStat)))

    remaining = {(row.bot_identity, row.scope_id) for row in rows}
    assert remaining == {
        (BotIdentity.CARI.value, "42:-100"),
        (BotIdentity.CARI.value, "42:-200"),
    }
    await database.close()
