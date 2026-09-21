from app.game.catalog import CHARACTERS
from app.game.waifu_art import art_path_for, declared_art_for_catalog


def test_art_registry_declares_every_playable_character() -> None:
    declared = declared_art_for_catalog()
    assert len(declared) == len(CHARACTERS)
    assert {item.character_id for item in declared} == set(CHARACTERS)


def test_art_registry_is_deterministic_and_character_specific() -> None:
    assert art_path_for("yor-forger") == "assets/waifus/yor-forger.png"
    assert art_path_for("anya") == "assets/waifus/anya.png"


def test_art_registry_rejects_unknown_character() -> None:
    try:
        art_path_for("not-a-character")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")
