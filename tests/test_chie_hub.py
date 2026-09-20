from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.chie.module import ChieModule


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("section", "expected"),
    (
        ("community", "/reglas"),
        ("games", "/juego"),
        ("content", "/catalogo"),
        ("points", "/puntos"),
        ("config", "/configurar"),
    ),
)
async def test_chie_hub_sections_are_actionable(section: str, expected: str) -> None:
    module = ChieModule.__new__(ChieModule)
    module._observe_action = AsyncMock()

    message = SimpleNamespace(
        edit_text=AsyncMock(),
        chat=SimpleNamespace(id=-100123, type="supergroup"),
    )
    callback = SimpleNamespace(
        message=message,
        from_user=SimpleNamespace(id=77),
        data=f"chie:hub:{section}",
        answer=AsyncMock(),
    )

    await module.command_hub(callback)

    message.edit_text.assert_awaited_once()
    body = message.edit_text.await_args.args[0]
    assert expected in body
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_chie_hub_home_returns_to_main_keyboard() -> None:
    module = ChieModule.__new__(ChieModule)

    message = SimpleNamespace(
        edit_text=AsyncMock(),
        chat=SimpleNamespace(id=-100123, type="supergroup"),
    )
    callback = SimpleNamespace(
        message=message,
        from_user=SimpleNamespace(id=77),
        data="chie:hub:home",
        answer=AsyncMock(),
    )

    await module.command_hub(callback)

    kwargs = message.edit_text.await_args.kwargs
    assert kwargs["reply_markup"] is not None
    callback.answer.assert_awaited_once()
