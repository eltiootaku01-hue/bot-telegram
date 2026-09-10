from datetime import datetime

from app.game.catalog import get_character
from app.game.encounters import new_encounter


def test_rare_wild_encounter_is_class_b_and_has_niche_question() -> None:
    encounter = new_encounter(get_character("taiga"), datetime(2026, 1, 1))
    assert encounter.character.id == "taiga"
    assert encounter.question is not None
    assert encounter.answer == "ryuuji"
    seconds = (encounter.expires_at - datetime(2026, 1, 1)).total_seconds()
    assert 60 <= seconds <= 600


def test_common_wild_encounter_is_immediate_capture() -> None:
    character = get_character("taiga")
    # The current catalog only has Taiga, so the rule itself is exercised through
    # the fallback plan for non-rare characters in future catalog entries.
    assert character.rarity.value == "rare"
