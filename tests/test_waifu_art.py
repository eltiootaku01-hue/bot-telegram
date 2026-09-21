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


def test_variant_art_registry_supports_normal_and_shiny_assets() -> None:
    from app.game.waifu_art import variant_art_candidates_for

    normal = variant_art_candidates_for("yor-forger", "normal")
    shiny = variant_art_candidates_for("yor-forger", "shiny")

    assert normal[0] == "assets/waifus/yor-forger--normal.png"
    assert shiny[0] == "assets/waifus/yor-forger--shiny.png"


def test_variant_art_registry_rejects_unknown_variant() -> None:
    from app.game.waifu_art import variant_art_candidates_for

    try:
        variant_art_candidates_for("yor-forger", "unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
