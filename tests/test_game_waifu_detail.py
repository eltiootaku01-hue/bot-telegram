from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.modules.game.module import GameModule


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_waifu_detail_returns_filtered_catalog_context(database: Database) -> None:
    module = GameModule(database, Settings(admin_user_id=77))
    callback_message = SimpleNamespace(
        chat=SimpleNamespace(id=77, type="private"),
        edit_text=AsyncMock(),
    )
    callback = SimpleNamespace(
        message=callback_message,
        from_user=SimpleNamespace(id=77),
        data="game:waifu:d:yor-forger:2:r:ss",
        answer=AsyncMock(),
    )

    await module.waifu_detail(callback)

    callback_message.edit_text.assert_awaited_once()
    rendered = callback_message.edit_text.await_args.args[0]
    markup = callback_message.edit_text.await_args.kwargs["reply_markup"]
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]

    assert "Yor Forger" in rendered
    assert "SPY x FAMILY" in rendered
    assert "Ranker" in rendered
    assert "game:waifus:page:2:r:ss" in callbacks
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_waifu_detail_rejects_unknown_character(database: Database) -> None:
    module = GameModule(database, Settings(admin_user_id=77))
    callback = SimpleNamespace(
        message=SimpleNamespace(
            chat=SimpleNamespace(id=77, type="private"),
            edit_text=AsyncMock(),
        ),
        from_user=SimpleNamespace(id=77),
        data="game:waifu:d:not-real:1",
        answer=AsyncMock(),
    )

    await module.waifu_detail(callback)

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "No encuentro esa waifu.",
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_waifu_detail_rejects_foreign_private_message(database: Database) -> None:
    module = GameModule(database, Settings(admin_user_id=77))
    callback = SimpleNamespace(
        message=SimpleNamespace(
            chat=SimpleNamespace(id=88, type="private"),
            edit_text=AsyncMock(),
        ),
        from_user=SimpleNamespace(id=77),
        data="game:waifu:d:yor-forger:1",
        answer=AsyncMock(),
    )

    await module.waifu_detail(callback)

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "Este catálogo solo funciona en tu chat privado con Sunna. 😰",
        show_alert=True,
    )
