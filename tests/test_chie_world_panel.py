from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.modules.chie.module import ChieModule
from app.services.world import WorldService


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_world_command_is_admin_private_only(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77))
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    denied = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=88),
        answer=answer,
    )
    await module.world_command(denied)
    assert answers == []


@pytest.mark.asyncio
async def test_world_command_reports_aggregate_signals(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77))
    world = WorldService()

    async with database.session() as session:
        await world.register_catalog_entry(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="anime",
            label="Anime",
            priority=10,
        )
        await world.observe(
            session,
            bot_identity=BotIdentity.CARI,
            entry_type="topic",
            entry_key="anime",
            delta=3,
        )

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=77),
        answer=answer,
    )
    await module.world_command(message)

    assert answers
    assert "Ciudad Animals" in answers[0]
    assert "anime (3)" in answers[0]
    assert "Cami" in answers[0]


@pytest.mark.asyncio
async def test_member_joined_welcomes_human_member_in_configured_community(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77, authorized_chat_ids="-100123"))
    bot = AsyncMock()

    async with database.session() as session:
        from app.db.community_models import SetupSession

        session.add(
            SetupSession(
                user_id=77,
                chat_id=-100123,
                bot_identity=BotIdentity.CHIE.value,
                status="configured",
            )
        )

    event = SimpleNamespace(
        chat=SimpleNamespace(id=-100123, type="supergroup"),
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=SimpleNamespace(id=99, is_bot=False, full_name="Nuevo Integrante"),
        ),
    )
    module.topics.get_thread_id = AsyncMock(return_value=456)

    await module.member_joined(event, bot)

    bot.send_message.assert_awaited_once()
    args = bot.send_message.await_args.args
    kwargs = bot.send_message.await_args.kwargs
    assert args[0] == -100123
    assert kwargs["message_thread_id"] == 456
    assert "Nuevo Integrante" in args[1]


@pytest.mark.asyncio
async def test_member_joined_ignores_bots(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77))
    bot = AsyncMock()
    event = SimpleNamespace(
        chat=SimpleNamespace(id=-100123, type="supergroup"),
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=SimpleNamespace(id=99, is_bot=True, full_name="Bot"),
        ),
    )

    await module.member_joined(event, bot)

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_rules_command_publishes_deterministic_rules(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77))
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="group", id=-100123),
        from_user=SimpleNamespace(id=77),
        answer=answer,
    )

    await module.rules_command(message)

    assert answers
    assert "Reglas de Ciudad Animals" in answers[0]
    assert "respeto" in answers[0].casefold()


@pytest.mark.asyncio
async def test_health_command_is_admin_private_only_and_returns_aggregate_report(database: Database) -> None:
    module = ChieModule(database, Settings(
        admin_user_id=77,
        authorized_chat_ids="-100123",
    ))
    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    async with database.session() as session:
        from app.db.community_models import SetupSession
        session.add(
            SetupSession(
                user_id=77,
                chat_id=-100123,
                bot_identity=BotIdentity.CHIE.value,
                status="configured",
            )
        )

    denied = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=88),
        from_user=SimpleNamespace(id=88),
        answer=answer,
    )
    await module.health_command(denied)
    assert answers == []

    owner = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        from_user=SimpleNamespace(id=77),
        answer=answer,
    )
    await module.health_command(owner)

    assert answers
    assert "Salud de Ciudad Animals" in answers[-1]
    assert "Comunidades configuradas: <b>1</b>" in answers[-1]
    assert "Comunidades autorizadas: <b>1</b>" in answers[-1]

@pytest.mark.asyncio
async def test_member_joined_skips_unauthorized_configured_community(database: Database) -> None:
    module = ChieModule(database, Settings(admin_user_id=77, authorized_chat_ids="-100123"))
    bot = AsyncMock()

    async with database.session() as session:
        from app.db.community_models import SetupSession
        session.add(
            SetupSession(
                user_id=77,
                chat_id=-100999,
                bot_identity=BotIdentity.CHIE.value,
                status="configured",
            )
        )

    event = SimpleNamespace(
        chat=SimpleNamespace(id=-100999, type="supergroup"),
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=SimpleNamespace(id=99, is_bot=False, full_name="Nuevo"),
        ),
    )

    await module.member_joined(event, bot)

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_world_proposal_decision_is_owner_only_and_single_use(database: Database) -> None:
    module = ChieModule(
        database,
        Settings(admin_user_id=77),
    )
    async with database.session() as session:
        from app.db.world_models import WorldProposal
        session.add(
            WorldProposal(
                review_id=1,
                generator="brain:ollama:test",
                status="pending",
                payload_json='{"proposals":[{"title":"Idea","idea":"Una escena.","reason":"Uso","affected_identities":[]}]}' ,
            )
        )

    denied = SimpleNamespace(
        message=SimpleNamespace(chat=SimpleNamespace(type="private", id=88)),
        from_user=SimpleNamespace(id=88),
        data="chie:world-proposal:accept:1",
        answer=AsyncMock(),
    )
    await module.world_proposal_decision(denied)
    denied.answer.assert_awaited_once()

    owner_message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
        edit_reply_markup=AsyncMock(),
        answer=AsyncMock(),
    )
    owner = SimpleNamespace(
        message=owner_message,
        from_user=SimpleNamespace(id=77),
        data="chie:world-proposal:accept:1",
        answer=AsyncMock(),
    )
    await module.world_proposal_decision(owner)

    async with database.session() as session:
        from app.db.world_models import WorldProposal
        row = await session.get(WorldProposal, 1)

    assert row is not None
    assert row.status == "accepted"
    owner.answer.assert_awaited_once()
    owner_message.edit_reply_markup.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_world_curator_requires_explicit_gate(database: Database) -> None:
    module = ChieModule(
        database,
        Settings(admin_user_id=77, ai_enabled=True, ai_enabled_chie=True),
    )
    module.bot = AsyncMock()

    await module._maybe_generate_daily_world_proposal(
        day_key="2026-09-24",
        report=SimpleNamespace(review_type="daily", period_key="2026-09-24"),
    )

    module.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_world_curator_notifies_admin_only_after_generation(database: Database) -> None:
    payload = (
        '{"proposals":[{"title":"Idea","idea":"Una escena pequena.",'
        '"reason":"Hay datos nuevos.","affected_identities":["cari"]}]}'
    )
    from app.brain.provider import LLMRequest
    from app.services.world_curator_ai import WorldCuratorAIService, format_world_proposals

    class FakeBrain:
        def __init__(self) -> None:
            self.requests: list[LLMRequest] = []

        async def generate(self, request: LLMRequest) -> str:
            self.requests.append(request)
            return payload

    settings = Settings(
        admin_user_id=77,
        ai_enabled=True,
        ai_enabled_chie=True,
        ai_curator_auto=True,
        ollama_model="test-model",
    )
    module = ChieModule(database, settings)
    brain = FakeBrain()
    module.curator_ai = WorldCuratorAIService(settings, brain=brain)  # type: ignore[arg-type]
    module.bot = AsyncMock()

    async with database.session() as session:
        report = await module.curator.build_daily(
            session,
            day_key="2026-09-25",
        )

    await module._maybe_generate_daily_world_proposal(
        day_key="2026-09-25",
        report=report,
    )

    module.bot.send_message.assert_awaited_once()
    assert module.bot.send_message.await_args.args[0] == 77
    assert len(brain.requests) == 1

    await module._maybe_generate_daily_world_proposal(
        day_key="2026-09-25",
        report=report,
    )
    assert len(brain.requests) == 1
    assert module.bot.send_message.await_count == 1
