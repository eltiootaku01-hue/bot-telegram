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
