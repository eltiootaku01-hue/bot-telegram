from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldCatalogEntry
from app.modules.system.module import SystemModule


@pytest.mark.asyncio
async def test_system_startup_seeds_shared_world_catalog(database=None):
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_schema()
    bot = AsyncMock()
    module = SystemModule(BotIdentity.SUNNA, db)

    await module.on_startup(bot)

    async with db.session() as session:
        rows = list(await session.scalars(select(WorldCatalogEntry)))

    assert rows
    assert {row.bot_identity for row in rows} == {identity.value for identity in BotIdentity}
    assert any(row.entry_key == "cafe_otaku" for row in rows)
    assert any(row.entry_key == "waifumon" for row in rows)
    await db.close()
