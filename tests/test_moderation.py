from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.models import ModerationAction
from app.modules.moderation.module import ModerationModule


@pytest.fixture
async def database(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'moderation.db'}")
    await database.create_schema()
    yield database
    await database.close()


def make_message(*, command: str, moderator_id: int = 10, target_id: int = 20):
    return SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="supergroup"),
        from_user=SimpleNamespace(id=moderator_id, is_bot=False, full_name="Moderador"),
        text=command,
        reply_to_message=SimpleNamespace(
            from_user=SimpleNamespace(id=target_id, is_bot=False, full_name="Integrante")
        ),
        answer=AsyncMock(),
    )


def make_bot():
    bot = AsyncMock()
    bot.get_me.return_value = SimpleNamespace(id=999)

    async def get_chat_member(chat_id, user_id):
        if user_id == 10:
            return SimpleNamespace(status="administrator")
        return SimpleNamespace(status="member", can_restrict_members=True)

    bot.get_chat_member.side_effect = get_chat_member
    return bot


@pytest.mark.asyncio
async def test_warning_is_admin_only_and_persisted(database: Database) -> None:
    module = ModerationModule(database)
    message = make_message(command="/advertir spam repetido")
    bot = make_bot()

    await module.warn(message, bot)

    async with database.session() as session:
        row = await session.scalar(select(ModerationAction))

    assert row is not None
    assert row.chat_id == -100
    assert row.target_user_id == 20
    assert row.moderator_user_id == 10
    assert row.action == "warn"
    assert row.reason == "spam repetido"
    assert "Advertencia" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_silence_restricts_member_and_records_expiry(database: Database) -> None:
    module = ModerationModule(database)
    message = make_message(command="/silenciar flood")
    bot = make_bot()

    await module.silence(message, bot)

    bot.restrict_chat_member.assert_awaited_once()
    assert bot.restrict_chat_member.await_args.args[:2] == (-100, 20)

    async with database.session() as session:
        row = await session.scalar(
            select(ModerationAction).where(ModerationAction.action == "silence")
        )

    assert row is not None
    assert row.reason == "flood"
    assert row.until_at is not None
    assert "10 minutos" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_moderation_refuses_target_that_is_an_administrator(database: Database) -> None:
    module = ModerationModule(database)
    message = make_message(command="/silenciar")
    bot = AsyncMock()
    bot.get_chat_member.side_effect = [
        SimpleNamespace(status="administrator"),
        SimpleNamespace(status="administrator"),
    ]

    await module.silence(message, bot)

    bot.restrict_chat_member.assert_not_awaited()
    message.answer.assert_awaited_once()
    assert "administrador" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_kick_bans_then_unbans_member(database: Database) -> None:
    module = ModerationModule(database)
    message = make_message(command="/expulsar reglas incumplidas")
    bot = make_bot()

    await module.kick(message, bot)

    bot.ban_chat_member.assert_awaited_once_with(-100, 20)
    bot.unban_chat_member.assert_awaited_once_with(-100, 20)
    async with database.session() as session:
        row = await session.scalar(
            select(ModerationAction).where(ModerationAction.action == "kick")
        )

    assert row is not None
    assert row.reason == "reglas incumplidas"


@pytest.mark.asyncio
async def test_moderation_requires_reply_to_a_real_user(database: Database) -> None:
    module = ModerationModule(database)
    message = make_message(command="/advertir")
    message.reply_to_message = None
    bot = make_bot()

    await module.warn(message, bot)

    bot.get_chat_member.assert_not_awaited()
    assert "Respondé al mensaje" in message.answer.await_args.args[0]
