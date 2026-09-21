from unittest.mock import AsyncMock

import pytest

from app.characters.models import CharacterIntent
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.stickers.catalog import STICKER_CATALOG, sticker_for, sticker_prompt


def test_sticker_catalog_covers_all_identities_and_core_intents() -> None:
    assert {spec.identity for spec in STICKER_CATALOG} == set(BotIdentity)
    for identity in BotIdentity:
        for intent in (
            CharacterIntent.GREETING,
            CharacterIntent.THANKS,
            CharacterIntent.AFFECTION,
            CharacterIntent.CELEBRATION,
            CharacterIntent.CONFUSION,
            CharacterIntent.GAME_SUCCESS,
            CharacterIntent.GAME_MISS,
        ):
            spec = sticker_for(identity, intent)
            assert spec is not None
            assert spec.identity is identity
            assert spec.intent is intent


def test_sticker_selection_is_deterministic() -> None:
    first = sticker_for(BotIdentity.SUNNA, CharacterIntent.GAME_SUCCESS, roll=42)
    second = sticker_for(BotIdentity.SUNNA, CharacterIntent.GAME_SUCCESS, roll=42)
    assert first == second


def test_sticker_prompt_is_safe_and_telegram_oriented() -> None:
    spec = sticker_for(BotIdentity.CARI, CharacterIntent.CELEBRATION)
    assert spec is not None
    prompt = sticker_prompt(spec).casefold()
    assert "telegram sticker" in prompt
    assert "fondo transparente" in prompt
    assert "no nudity" in prompt or "sin desnudez" in prompt
    assert "no sexualized pose" in prompt or "sin pose sexualizada" in prompt
    assert "no gore" in prompt or "sin gore" in prompt


def test_sticker_keys_are_unique() -> None:
    keys = [spec.key for spec in STICKER_CATALOG]
    assert len(keys) == len(set(keys))
    assert len(STICKER_CATALOG) == 48


def test_sticker_service_resolves_configured_file_id() -> None:
    from app.stickers.service import StickerService

    settings = Settings(
        telegram_sticker_file_ids_json='{"cari-celebration-01":"CAAC123"}'
    )
    service = StickerService(settings)
    assert service.file_id_for(
        BotIdentity.CARI,
        CharacterIntent.CELEBRATION,
    ) == "CAAC123"


@pytest.mark.asyncio
async def test_sticker_service_sends_only_when_configured() -> None:
    from app.stickers.service import StickerService

    settings = Settings()
    service = StickerService(settings)
    bot = AsyncMock()
    message = AsyncMock()

    sent = await service.send_if_configured(
        bot,
        message,
        BotIdentity.CARI,
        CharacterIntent.CELEBRATION,
    )

    assert sent is False
    bot.send_sticker.assert_not_awaited()
