from types import SimpleNamespace
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
    assert {"juego", "gacha", "inventario", "combate", "misterio", "trivia", "puntos", "ranking"} <= names


@pytest.mark.asyncio
async def test_chie_command_menu_exposes_world_metrics_command() -> None:
    module = SystemModule(BotIdentity.CHIE)
    bot = AsyncMock()
    await module.on_startup(bot)

    commands = bot.set_my_commands.await_args.args[0]
    names = {command.command for command in commands}

    assert "mundo" in names
    assert "revisar_mundo" in names
    assert "proponer_mundo" in names
    assert "comandos" in names
    assert "configurar" in names

@pytest.mark.asyncio
async def test_help_surface_is_identity_aware() -> None:
    for identity, expected in (
        (BotIdentity.CARI, "/cafe"),
        (BotIdentity.CAMI, "/catalogo"),
        (BotIdentity.CHIE, "/configurar"),
    ):
        module = SystemModule(identity)
        message = SimpleNamespace(answer=AsyncMock())

        await module.help(message)

        rendered = message.answer.await_args.args[0]
        assert identity.value.title() in rendered
        assert expected in rendered



@pytest.mark.asyncio
async def test_sunna_command_menu_exposes_daily_missions() -> None:
    module = SystemModule(BotIdentity.SUNNA)
    bot = AsyncMock()
    await module.on_startup(bot)

    commands = bot.set_my_commands.await_args.args[0]
    names = {command.command for command in commands}

    assert "misiones" in names
