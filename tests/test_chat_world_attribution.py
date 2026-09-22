from types import SimpleNamespace
from unittest.mock import AsyncMock

from unittest.mock import AsyncMock


import pytest
from sqlalchemy import select

from app.characters.models import CharacterIntent
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.db.world_models import WorldUsageStat
from app.modules.chat.module import ChatModule
from app.modules.system.module import SystemModule


class FakeTargetSession:
    async def close(self) -> None:
        return None


class FakeTargetBot:
    def __init__(self) -> None:
        self.session = FakeTargetSession()
        self.sent: list[tuple[int, str, int | None]] = []

    async def send_message(self, chat_id: int, text: str, message_thread_id: int | None = None) -> None:
        self.sent.append((chat_id, text, message_thread_id))


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
        text="bot",
        answer=answer,
    )

    await module.handle_text(message, AsyncMock())

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
    await sunna.handle_text(message, AsyncMock())

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
    module = ChatModule(
        database,
        identity=BotIdentity.CAMI,
        settings=Settings(bot_token_sunna='sunna-test-token'),
        bot_factory=lambda token: FakeTargetBot(),
    )
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
    await module.handle_text(message, AsyncMock())

    assert len(answers) == 1
    assert answers[0] in {
        "Sunna, si quieres podemos revisarlo juntas. Sin prisa.",
        "Sunna, si querés, te muestro cómo funciona este juego.",
    }


@pytest.mark.asyncio
async def test_interaction_usage_is_recorded_as_relationship(database: Database) -> None:
    target_bots: list[FakeTargetBot] = []

    def factory(token: str) -> FakeTargetBot:
        bot = FakeTargetBot()
        target_bots.append(bot)
        return bot

    module = ChatModule(
        database,
        settings=Settings(bot_token_cami='cami-test-token'),
        bot_factory=factory,
    )

    async def answer(text: str) -> None:
        return None

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=-100),
        text="Cari, Cami, no entiendo",
        answer=answer,
    )

    await module.handle_text(message, AsyncMock())

    assert target_bots

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
    target_bots: list[FakeTargetBot] = []

    def factory(token: str) -> FakeTargetBot:
        bot = FakeTargetBot()
        target_bots.append(bot)
        return bot

    module = ChatModule(
        database,
        identity=BotIdentity.CAMI,
        settings=Settings(bot_token_sunna="sunna-test-token"),
        bot_factory=factory,
    )
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        chat=SimpleNamespace(id=11, type="supergroup"),
        text="Cami Sunna no entiendo",
        answer=answer,
    )

    await module.handle_text(message, AsyncMock())
    first_source = list(answers)
    first_followup = target_bots[-1].sent[0][1]

    answers.clear()
    await module.handle_text(message, AsyncMock())
    second_source = list(answers)
    second_followup = target_bots[-1].sent[0][1]

    assert first_source
    assert second_source
    assert first_followup
    assert second_followup
    assert first_source[0] != second_source[0]
    assert first_followup != second_followup

    async with database.session() as session:
        count = await module.world.usage_count(
            session,
            bot_identity=BotIdentity.CAMI,
            entry_type="relationship",
            entry_key="cami-sunna",
            scope_type="user_chat",
            scope_id="7:11",
        )

    assert count == 2



@pytest.mark.asyncio
async def test_interaction_follow_up_uses_target_identity_transport_and_forum_thread(database: Database) -> None:
    from app.core.config import Settings

    source_answers: list[str] = []
    target_sent: list[tuple[int, str, int | None]] = []

    class FakeSession:
        async def close(self) -> None:
            return None

    class FakeTargetBot:
        def __init__(self) -> None:
            self.session = FakeSession()

        async def send_message(self, chat_id: int, text: str, message_thread_id: int | None = None) -> None:
            target_sent.append((chat_id, text, message_thread_id))

    module = ChatModule(
        database,
        identity=BotIdentity.CAMI,
        settings=Settings(bot_token_sunna="sunna-test-token"),
        bot_factory=lambda token: FakeTargetBot(),
    )

    async def answer(text: str) -> None:
        source_answers.append(text)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=-100, type="supergroup"),
        message_thread_id=1234,
        text="Cami y Sunna, una pregunta",
        answer=answer,
    )

    await module.handle_text(message, AsyncMock())

    assert len(source_answers) == 1
    assert source_answers[0] in {
        "Sunna, si quieres podemos revisarlo juntas. Sin prisa.",
        "Sunna, si querés, te muestro cómo funciona este juego.",
    }
    assert target_sent
    assert target_sent[0][0] == -100
    assert target_sent[0][2] == 1234
    assert target_sent[0][1] in {
        "Sí... me gustaría.",
        "Sí. Quiero aprender.",
    }


@pytest.mark.asyncio
async def test_missing_partner_token_does_not_fake_a_second_speaker_message(database: Database) -> None:
    source_answers: list[str] = []

    async def answer(text: str) -> None:
        source_answers.append(text)

    module = ChatModule(database, identity=BotIdentity.CAMI)

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(id=-100, type="supergroup"),
        text="Cami y Sunna, una pregunta",
        answer=answer,
    )

    await module.handle_text(message, AsyncMock())

    assert len(source_answers) == 1

    async with database.session() as session:
        rows = list(
            await session.scalars(
                select(WorldUsageStat).where(WorldUsageStat.entry_type == "relationship")
            )
        )
    assert rows == []


def test_chie_owns_generic_greetings_and_farewells() -> None:
    from app.core.config import Settings

    chie = ChatModule(Database("sqlite+aiosqlite:///:memory:"), identity=BotIdentity.CHIE, settings=Settings())
    cari = ChatModule(Database("sqlite+aiosqlite:///:memory:"), identity=BotIdentity.CARI, settings=Settings())
    sunna = ChatModule(Database("sqlite+aiosqlite:///:memory:"), identity=BotIdentity.SUNNA, settings=Settings())

    assert chie._should_handle_text("hola") is True
    assert chie._should_handle_text("me voy") is True
    assert cari._should_handle_text("hola") is False
    assert sunna._should_handle_text("hola") is False


@pytest.mark.asyncio
async def test_cross_bot_authored_send_rechecks_group_allowlist(database: Database) -> None:
    from app.core.config import Settings

    module = ChatModule(
        database,
        identity=BotIdentity.CARI,
        settings=Settings(authorized_chat_ids="-100123"),
    )
    message = SimpleNamespace(
        chat=SimpleNamespace(
            id=-100999,
            type="supergroup",
            message_thread_id=None,
        )
    )
    bot_factory = AsyncMock()
    target_bot = AsyncMock()
    bot_factory.return_value = target_bot
    module.bot_factory = bot_factory

    sent = await module._send_authored_text(
        message,
        AsyncMock(),
        BotIdentity.CAMI,
        "test",
    )

    assert sent is False
    target_bot.send_message.assert_not_awaited()
