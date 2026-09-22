from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.command_center.models import CafeTable, ManualMessageCommand, TemporaryMessagePolicy
from app.command_center.telegram_gateway import TelegramGateway


def test_temporary_message_policy_is_bounded() -> None:
    policy = TemporaryMessagePolicy()
    assert policy.delay_for("hola") >= policy.minimum_seconds
    assert policy.delay_for("x" * 2000) == policy.maximum_seconds


def test_cafe_table_carries_forum_topic_coordinates() -> None:
    table = CafeTable(
        key="mesa-anime",
        label="Mesa Anime",
        chat_id=-100,
        message_thread_id=42,
        x=120,
        y=240,
    )
    assert table.message_thread_id == 42
    assert table.x == 120
    assert table.y == 240


@pytest.mark.asyncio
async def test_gateway_protects_card_content_by_default(tmp_path: Path) -> None:
    asset = tmp_path / "card.jpg"
    asset.write_bytes(b"fake")

    bot = AsyncMock()
    bot.send_photo.return_value = SimpleNamespace(message_id=99)
    gateway = TelegramGateway({"sunna": bot})

    await gateway.send_card(
        identity="sunna",
        chat_id=-100,
        asset_path=str(asset),
        caption="#001 Rei Ayanami R",
    )

    kwargs = bot.send_photo.await_args.kwargs
    assert kwargs["protect_content"] is True
    assert kwargs["caption"] == "#001 Rei Ayanami R"


@pytest.mark.asyncio
async def test_gateway_passes_forum_topic_and_typing() -> None:
    bot = AsyncMock()
    bot.send_message.return_value = SimpleNamespace(message_id=10)
    gateway = TelegramGateway({"cari": bot})
    command = ManualMessageCommand(
        identity="cari",
        chat_id=-100,
        message_thread_id=77,
        text="hola mesa",
    )

    await gateway.typing("cari", -100)
    await gateway.send_text(command)

    bot.send_chat_action.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["message_thread_id"] == 77
