from unittest.mock import AsyncMock

import pytest

from app.core.identity import BotIdentity
from app.modules.system.module import SystemModule


@pytest.mark.asyncio
async def test_sunna_command_menu_does_not_advertise_removed_request_command() -> None:
    module = SystemModule(BotIdentity.SUNNA)
    bot = AsyncMock()
    await module.on_startup(bot)

    commands = bot.set_my_commands.await_args.args[0]
    names = {command.command for command in commands}

    assert "pedido" not in names
    assert {"juego", "gacha", "inventario", "combate", "trivia", "puntos", "ranking"} <= names


@pytest.mark.asyncio
async def test_chie_command_menu_exposes_world_metrics_command() -> None:
    module = SystemModule(BotIdentity.CHIE)
    bot = AsyncMock()
    await module.on_startup(bot)

    commands = bot.set_my_commands.await_args.args[0]
    names = {command.command for command in commands}

    assert "mundo" in names
    assert "comandos" in names
    assert "configurar" in names


@pytest.mark.asyncio
async def test_chie_world_command_reports_catalog_and_usage() -> None:
    from types import SimpleNamespace

    from app.db.database import Database
    from app.db.world_models import WorldUsageStat

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    module = SystemModule(BotIdentity.CHIE, database)
    async with database.session() as session:
        await module.world.seed_catalog(session)
        await module.world.observe(
            session,
            bot_identity=BotIdentity.CHIE,
            entry_type="action",
            entry_key="welcome",
            delta=3,
        )

    answers: list[str] = []

    async def answer(text: str) -> None:
        answers.append(text)

    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup"),
        answer=answer,
    )

    await module.world_command(message)

    assert answers
    assert "Ciudad Animals" in answers[0]
    assert "welcome" in answers[0]
    await database.close()
