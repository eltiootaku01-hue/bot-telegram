from types import SimpleNamespace

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldUsageStat
from app.modules.chat.module import ChatModule
from app.modules.system.module import SystemModule


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
        chat=SimpleNamespace(id=39),
        text="Sunna",
        answer=answer,
    )
    await sunna.handle_text(message)

    assert answers == ["¿Sí?"]


@pytest.mark.asyncio
async def test_system_startup_seeds_world_catalog(database: Database) -> None:
    module = SystemModule(BotIdentity.SUNNA, database)
    await module.on_startup(AsyncMock())

    async with database.session() as session:
        rows = list(await session.scalars(select(WorldUsageStat)))
        from app.db.world_models import WorldCatalogEntry
        catalog = list(await session.scalars(select(WorldCatalogEntry)))

    assert rows == []
    assert any(entry.entry_key == "cafe_otaku" for entry in catalog)
    assert any(entry.entry_key == "waifumon" for entry in catalog)
    assert any(entry.entry_key == "cari-cami" for entry in catalog)
    assert any(entry.entry_key == "chie-sunna" for entry in catalog)


@pytest.mark.asyncio
async def test_non_cari_character_chat_leaves_complex_addressed_prompt_for_brain(database: Database) -> None:
    from app.core.identity import BotIdentity

    sunna = ChatModule(database, identity=BotIdentity.SUNNA)

    assert sunna._should_handle_text("Sunna, explicame cómo funciona el gacha") is False
    assert sunna._should_handle_text("Sunna") is True


@pytest.mark.asyncio
async def test_chat_uses_authored_pair_scene_without_generating_a_second_independent_reply(
    database: Database,
) -> None:
    module = ChatModule(database, identity=BotIdentity.CAMI)
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=99),
        text="Cami y Sunna, una pregunta",
        answer=answer,
    )

    assert module._should_handle_text(message.text) is True
    await module.handle_text(message)

    assert len(answers) == 2
    assert answers[0] in {
        "Sunna, si quieres podemos revisarlo juntas. Sin prisa.",
        "Sunna, si querés, te muestro cómo funciona este juego.",
    }
    assert answers[1] in {
        "Sí... me gustaría.",
        "Sí. Quiero aprender.",
    }


@pytest.mark.asyncio
async def test_interaction_usage_is_recorded_as_relationship(database: Database) -> None:
    module = ChatModule(database)

    async def answer(text: str) -> None:
        return None

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=-100),
        text="Cari, Cami, no entiendo",
        answer=answer,
    )

    await module.handle_text(message)

    async with database.session() as session:
        rows = list(await session.scalars(
            select(WorldUsageStat).where(
                WorldUsageStat.entry_type == "relationship",
                WorldUsageStat.scope_type == "world",
            )
        ))

    assert any(row.entry_key == "cari-cami" and row.count == 1 for row in rows)


@pytest.mark.asyncio
async def test_directed_interaction_uses_persisted_relationship_count_to_rotate_authored_scene(
    database: Database,
) -> None:
    module = ChatModule(database)
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        chat=SimpleNamespace(id=11, type="supergroup"),
        text="Cami Sunna no entiendo",
        answer=answer,
    )

    await module.handle_text(message)
    first = list(answers)

    answers.clear()
    await module.handle_text(message)
    second = list(answers)

    assert first
    assert second
    assert first[0] != second[0]
    assert first[1] != second[1]

    async with database.session() as session:
        count = await module.world.usage_count(
            session,
            bot_identity=BotIdentity.CAMI,
            entry_type="relationship",
            entry_key="cami-sunna",
        )

    assert count == 2
