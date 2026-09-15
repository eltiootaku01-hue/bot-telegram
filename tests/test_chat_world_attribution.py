from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldUsageStat
from app.modules.chat.module import ChatModule


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_follow_up_scene_usage_is_attributed_to_real_speaker(database: Database) -> None:
    module = ChatModule(database)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=99),
    )

    await module._observe_scene(
        message,
        "cari-unknown-1:follow-up",
        CharacterIntent.UNKNOWN_TOPIC,
        BotIdentity.CAMI,
        "Estoy aquí. ¿Qué necesitas comprobar?",
    )

    async with database.session() as session:
        rows = (await session.scalars(select(WorldUsageStat))).all()

    assert len([row for row in rows if row.entry_type == "scene"]) >= 2
    scene_world_rows = {
        row.bot_identity: row
        for row in rows
        if row.entry_type == "scene" and row.scope_type == "world"
    }
    assert scene_world_rows[BotIdentity.CAMI].count == 1


@pytest.mark.asyncio
async def test_user_intent_remains_bound_to_cari_requester(database: Database) -> None:
    module = ChatModule(database)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        chat=SimpleNamespace(id=11),
    )

    await module._observe_scene(
        message,
        "cari-unknown-1:follow-up",
        CharacterIntent.UNKNOWN_TOPIC,
        BotIdentity.CAMI,
        "Estoy aquí. ¿Qué necesitas comprobar?",
    )

    async with database.session() as session:
        rows = (await session.scalars(select(WorldUsageStat))).all()

    intent_rows = [row for row in rows if row.entry_type == "intent"]
    assert len(intent_rows) == 1
    assert intent_rows[0].bot_identity is BotIdentity.CARI
    assert intent_rows[0].scope_type == "user"
    assert intent_rows[0].scope_id == "7"
