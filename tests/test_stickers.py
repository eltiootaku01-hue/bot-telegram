from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity
from app.stickers.catalog import STICKER_CATALOG, sticker_for, sticker_prompt

def test_sticker_catalog_covers_all_identities_and_core_intents() -> None:
    assert {spec.identity for spec in STICKER_CATALOG} == set(BotIdentity)
    for identity in BotIdentity:
        for intent in (CharacterIntent.GREETING, CharacterIntent.THANKS, CharacterIntent.AFFECTION, CharacterIntent.CELEBRATION, CharacterIntent.CONFUSION, CharacterIntent.GAME_SUCCESS, CharacterIntent.GAME_MISS):
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
    assert "sin desnudez" in prompt
    assert "sin pose sexualizada" in prompt
    assert "sin gore" in prompt

def test_sticker_keys_are_unique() -> None:
    keys = [spec.key for spec in STICKER_CATALOG]
    assert len(keys) == len(set(keys))
    assert len(STICKER_CATALOG) == 48