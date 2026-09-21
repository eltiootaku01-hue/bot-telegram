import pytest

from app.game.models import Character, Element, Rarity
from app.game.waifumon_progression import (
    CombatStyle,
    EvolutionStage,
    combat_style_for_element,
    evolution_band_for_level,
    evolution_next_level,
    stats_for_character,
)


def _character(element: Element, rarity: Rarity = Rarity.B, power: int = 50) -> Character:
    return Character(
        id=f"test-{element.value}-{rarity.value}-{power}",
        name="Test Waifu",
        anime="Ciudad Animals",
        rarity=rarity,
        element=element,
        popularity_score=50,
        power_score=power,
    )


@pytest.mark.parametrize(
    ("level", "stage", "next_level"),
    [
        (1, EvolutionStage.BASE, 6),
        (5, EvolutionStage.BASE, 6),
        (6, EvolutionStage.EVOLUTION_1, 11),
        (10, EvolutionStage.EVOLUTION_1, 11),
        (11, EvolutionStage.EVOLUTION_2, 21),
        (20, EvolutionStage.EVOLUTION_2, 21),
        (21, EvolutionStage.EVOLUTION_3, None),
        (30, EvolutionStage.EVOLUTION_3, None),
    ],
)
def test_level_maps_to_four_evolution_stages(level, stage, next_level) -> None:
    band = evolution_band_for_level(level)
    assert band.stage is stage
    assert evolution_next_level(stage) == next_level


@pytest.mark.parametrize("level", [0, 31])
def test_evolution_stage_rejects_invalid_levels(level) -> None:
    with pytest.raises(ValueError):
        evolution_band_for_level(level)


def test_rarity_is_independent_from_level() -> None:
    character = _character(Element.NEUTRAL, Rarity.S)
    level_one = stats_for_character(character, 1, rarity=Rarity.S, potential_seed="fixed")
    level_twenty = stats_for_character(character, 20, rarity=Rarity.S, potential_seed="fixed")

    assert level_one.rarity is Rarity.S
    assert level_twenty.rarity is Rarity.S
    assert level_one.evolution_stage is EvolutionStage.BASE
    assert level_twenty.evolution_stage is EvolutionStage.EVOLUTION_2
    assert level_twenty.level == 20
    assert level_twenty.strength > level_one.strength


def test_class_changes_stats_independently_of_level() -> None:
    character = _character(Element.NEUTRAL, Rarity.B)
    r20 = stats_for_character(character, 20, rarity=Rarity.D, potential_seed="fixed")
    s20 = stats_for_character(character, 20, rarity=Rarity.S, potential_seed="fixed")

    assert r20.level == s20.level == 20
    assert s20.rarity is Rarity.S
    assert r20.rarity is Rarity.D
    assert s20.max_hp > r20.max_hp
    assert s20.strength > r20.strength
    assert s20.defense > r20.defense
    assert s20.speed > r20.speed


def test_same_potential_seed_is_reproducible() -> None:
    character = _character(Element.LIGHTNING, Rarity.A)
    first = stats_for_character(character, 12, potential_seed="potential-42")
    second = stats_for_character(character, 12, potential_seed="potential-42")
    assert first == second


def test_different_potential_seeds_can_produce_different_stats() -> None:
    character = _character(Element.LIGHTNING, Rarity.A)
    first = stats_for_character(character, 12, potential_seed="potential-a")
    second = stats_for_character(character, 12, potential_seed="potential-b")
    assert first != second
    assert first.potential_score != second.potential_score or first.strength != second.strength


@pytest.mark.parametrize(
    ("element", "style"),
    [
        (Element.WIND, CombatStyle.SPEED),
        (Element.EARTH, CombatStyle.DURABILITY),
        (Element.FIRE, CombatStyle.FIRE_SPECIAL),
        (Element.WATER, CombatStyle.HEALING),
        (Element.NEUTRAL, CombatStyle.BRUTE_FORCE),
        (Element.ICE, CombatStyle.CONTROL),
        (Element.LIGHT, CombatStyle.SUPPORT),
        (Element.DARK, CombatStyle.CRITICAL),
        (Element.LIGHTNING, CombatStyle.BURST),
        (Element.MIND, CombatStyle.PRECISION),
        (Element.ARCANE, CombatStyle.ARCANE),
    ],
)
def test_elements_map_to_a_fighting_specialty(element, style) -> None:
    assert combat_style_for_element(element) is style


def test_wind_focuses_speed() -> None:
    stats = stats_for_character(_character(Element.WIND), 12, rarity=Rarity.B, potential_seed="fixed")
    assert stats.speed > stats.strength


def test_earth_focuses_durability() -> None:
    stats = stats_for_character(_character(Element.EARTH), 12, rarity=Rarity.B, potential_seed="fixed")
    assert stats.max_hp > stats.speed
    assert stats.defense > stats.speed


def test_fire_focuses_fire_skill() -> None:
    stats = stats_for_character(_character(Element.FIRE), 12, rarity=Rarity.B, potential_seed="fixed")
    assert stats.fire_skill > stats.strength
    assert stats.special_power > 25


def test_water_focuses_healing() -> None:
    stats = stats_for_character(_character(Element.WATER), 12, rarity=Rarity.B, potential_seed="fixed")
    assert stats.healing > stats.strength


def test_physical_focuses_raw_strength() -> None:
    stats = stats_for_character(_character(Element.NEUTRAL), 12, rarity=Rarity.B, potential_seed="fixed")
    assert stats.strength > stats.defense
