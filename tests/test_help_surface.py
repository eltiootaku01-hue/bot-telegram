from unittest.mock import AsyncMock

import pytest

from app.core.identity import BotIdentity
from app.modules.system.module import SystemModule
from app.ui.help_keyboards import help_keyboard


@pytest.mark.parametrize(
    ("identity", "expected"),
    (
        (BotIdentity.CARI, "help:cari:cafe"),
        (BotIdentity.SUNNA, "help:sunna:games"),
        (BotIdentity.CAMI, "help:cami:catalog"),
        (BotIdentity.CHIE, "help:chie:configure"),
    ),
)
def test_help_home_keyboard_is_identity_scoped(identity: BotIdentity, expected: str) -> None:
    keyboard = help_keyboard(identity)
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert expected in callbacks
    assert all(
        callback.startswith(f"help:{identity.value}:")
        for callback in callbacks
        if callback is not None
    )


@pytest.mark.asyncio
async def test_help_navigation_renders_section_for_current_identity() -> None:
    module = SystemModule(BotIdentity.CAMI)
    callback = AsyncMock()
    callback.message = AsyncMock()
    callback.from_user = AsyncMock()
    callback.data = "help:cami:catalog"

    await module.help_navigation(callback)

    rendered = callback.message.edit_text.await_args.args[0]
    assert "Catálogo" in rendered
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_help_navigation_rejects_foreign_identity() -> None:
    module = SystemModule(BotIdentity.CAMI)
    callback = AsyncMock()
    callback.message = AsyncMock()
    callback.from_user = AsyncMock()
    callback.data = "help:sunna:games"

    await module.help_navigation(callback)

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "Esta ayuda pertenece a otra identidad.",
        show_alert=True,
    )
