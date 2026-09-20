from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.modules.cafe.module import CafeModule
from app.ui.cafe_keyboards import cafe_menu_keyboard


def _button_data(markup):
    return [
        button
        for row in markup.inline_keyboard
        for button in row
    ]


def test_cafe_keyboard_keeps_local_recommendation_and_configured_bot_links() -> None:
    settings = Settings(
        bot_link_sunna="https://t.me/SunnaBot",
        bot_link_cami="https://t.me/CamiBot",
    )

    buttons = _button_data(cafe_menu_keyboard(settings))
    labels = {button.text for button in buttons}
    urls = {button.url for button in buttons if button.url}

    assert "🍿 Recomendación" in labels
    assert "🎮 Abrir Sunna" in labels
    assert "📚 Abrir Cami" in labels
    assert "📋 Abrir Chie" not in labels
    assert urls == {"https://t.me/SunnaBot", "https://t.me/CamiBot"}


@pytest.mark.asyncio
async def test_cafe_recommendation_callback_reuses_deterministic_recommendation() -> None:
    module = CafeModule.__new__(CafeModule)
    module.recommendation = AsyncMock()
    callback = SimpleNamespace(
        message=SimpleNamespace(),
        from_user=SimpleNamespace(id=7),
        answer=AsyncMock(),
    )

    await module.recommendation_callback(callback)

    module.recommendation.assert_awaited_once_with(callback.message)
    callback.answer.assert_awaited_once()
