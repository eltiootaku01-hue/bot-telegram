from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database
from app.modules.system.module import SystemModule


def _chat_member_event(chat_id: int, *, chat_type: str = "supergroup") -> SimpleNamespace:
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=SimpleNamespace(id=99, is_bot=False, full_name="Nuevo"),
        ),
    )


@pytest.mark.asyncio
async def test_system_bot_added_skips_unauthorized_community() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    module = SystemModule(
        BotIdentity.CARI,
        database,
        Settings(authorized_chat_ids="-100123"),
    )
    bot = AsyncMock()

    await module.bot_added(_chat_member_event(-100999), bot)

    bot.send_message.assert_not_awaited()
    await database.close()


@pytest.mark.asyncio
async def test_system_bot_added_publishes_to_authorized_community() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    module = SystemModule(
        BotIdentity.CARI,
        database,
        Settings(authorized_chat_ids="-100123"),
    )
    bot = AsyncMock()

    await module.bot_added(_chat_member_event(-100123), bot)

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == -100123
    await database.close()


@pytest.mark.asyncio
async def test_sunna_bot_added_keeps_game_keyboard_on_authorized_chat() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    module = SystemModule(
        BotIdentity.SUNNA,
        database,
        Settings(authorized_chat_ids="-100123"),
    )
    bot = AsyncMock()

    await module.bot_added(_chat_member_event(-100123), bot)

    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["reply_markup"] is not None
    await database.close()
