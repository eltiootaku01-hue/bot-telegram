from datetime import datetime

from app.game.catalog import get_character, wild_characters
from app.game.encounters import encounter_options, new_encounter


def test_class_b_wild_plan_requires_niche_question() -> None:
    encounter = new_encounter(get_character("taiga"), datetime(2026, 1, 1))
    assert encounter.character.id == "taiga"
    assert encounter.character.rarity.value == "B"
    assert encounter.question is not None
    assert encounter.answer == "ryuuji"
    seconds = (encounter.expires_at - datetime(2026, 1, 1)).total_seconds()
    assert 60 <= seconds <= 600


def test_question_options_contain_the_correct_answer() -> None:
    encounter = new_encounter(get_character("taiga"), datetime(2026, 1, 1))
    options = encounter_options(encounter)
    assert options == ["ryuuji", "kitamura", "ami"]
    assert encounter.answer in options


def test_public_wild_catalog_excludes_b_and_above() -> None:
    assert all(character.rarity.value in {"D", "C"} for character in wild_characters())


def test_common_wild_encounter_is_immediate_capture() -> None:
    encounter = new_encounter(get_character("anya"), datetime(2026, 1, 1))
    assert encounter.character.rarity.value == "D"
    assert encounter.question is None
    assert encounter.answer == "capture"
    assert encounter_options(encounter) == ["Anya"]
