from types import SimpleNamespace

import pytest
from sqlalchemy import select

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
    assert intent_rows[0].bot_identity == BotIdentity.CARI.value
    assert intent_rows[0].scope_type == "user"
    assert intent_rows[0].scope_id == "7"


@pytest.mark.asyncio
async def test_handle_text_persists_world_observation_after_authored_response(
    database: Database,
) -> None:
    module = ChatModule(database)
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        chat=SimpleNamespace(id=11),
        text="hola",
        answer=answer,
    )

    await module.handle_text(message)

    assert answers
    async with database.session() as session:
        rows = (await session.scalars(select(WorldUsageStat))).all()

    scene_rows = [row for row in rows if row.entry_type == "scene" and row.scope_type == "world"]
    intent_rows = [row for row in rows if row.entry_type == "intent"]
    user_scene_rows = [row for row in rows if row.entry_type == "scene" and row.scope_type == "user_chat"]

    assert scene_rows
    assert len(intent_rows) == 1
    assert intent_rows[0].bot_identity == BotIdentity.CARI.value
    assert intent_rows[0].scope_id == "7"
    assert user_scene_rows
    assert user_scene_rows[0].scope_id == "7:11"


@pytest.mark.asyncio
async def test_non_cari_character_chat_requires_explicit_address(database: Database) -> None:
    from app.core.identity import BotIdentity

    sunna = ChatModule(database, identity=BotIdentity.SUNNA)
    assert sunna._should_handle_text("hola") is False
    assert sunna._should_handle_text("Sunna") is True

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=12),
        chat=SimpleNamespace(id=44),
        text="Sunna",
        answer=answer,
    )
    await sunna.handle_text(message)

    assert answers == ["¿Sí?"]


@pytest.mark.asyncio
async def test_chat_startup_seeds_world_catalog(database: Database) -> None:
    module = ChatModule(database)
    await module.on_startup(None)

    async with database.session() as session:
        rows = list(await session.scalars(select(WorldUsageStat)))
        from app.db.world_models import WorldCatalogEntry
        catalog = list(await session.scalars(select(WorldCatalogEntry)))

    assert rows == []
    assert any(entry.entry_key == "cafe_otaku" for entry in catalog)
    assert any(entry.entry_key == "waifumon" for entry in catalog)
    assert any(entry.entry_key == "cari-cami" for entry in catalog)
    assert any(entry.entry_key == "chie-sunna" for entry in catalog)
