import pytest

from app.game.models import Character, Element, Rarity
from app.game.waifumon_progression import (
    CombatStyle,
    WaifuMonClass,
    class_band_for_level,
    combat_style_for_element,
    stats_for_character,
    waifumon_class_for_level,
)


def _character(element: Element) -> Character:
    return Character(
        id=f"test-{element.value}",
        name="Test Waifu",
        anime="Ciudad Animals",
        rarity=Rarity.B,
        element=element,
        popularity_score=50,
        power_score=50,
    )


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (1, WaifuMonClass.R),
        (10, WaifuMonClass.R),
        (11, WaifuMonClass.S),
        (20, WaifuMonClass.S),
        (21, WaifuMonClass.SR),
        (30, WaifuMonClass.SR),
    ],
)
def test_waifumon_class_promotes_by_level(level, expected) -> None:
    assert waifumon_class_for_level(level) is expected


@pytest.mark.parametrize("level", [0, 31])
def test_waifumon_class_rejects_invalid_levels(level) -> None:
    with pytest.raises(ValueError):
        class_band_for_level(level)


def test_s_level_11_is_stronger_than_r_level_10_but_lower_than_sr_level_21() -> None:
    character = _character(Element.NEUTRAL)

    r10 = stats_for_character(character, 10)
    s11 = stats_for_character(character, 11)
    sr21 = stats_for_character(character, 21)

    assert r10.waifumon_class is WaifuMonClass.R
    assert s11.waifumon_class is WaifuMonClass.S
    assert sr21.waifumon_class is WaifuMonClass.SR

    for field in (
        "max_hp",
        "strength",
        "defense",
        "speed",
        "healing",
        "special_power",
        "fire_skill",
        "critical_rate",
    ):
        assert getattr(r10, field) < getattr(s11, field)
        assert getattr(s11, field) < getattr(sr21, field)


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
def test_elements_map_to_a_distinct_fighting_specialty(element, style) -> None:
    assert combat_style_for_element(element) is style


def test_wind_focuses_speed() -> None:
    stats = stats_for_character(_character(Element.WIND), 11)
    assert stats.speed > stats.strength


def test_earth_focuses_durability() -> None:
    stats = stats_for_character(_character(Element.EARTH), 11)
    assert stats.max_hp > 135
    assert stats.defense > stats.speed


def test_fire_focuses_fire_skill() -> None:
    stats = stats_for_character(_character(Element.FIRE), 11)
    assert stats.fire_skill > stats.strength
    assert stats.special_power > 25


def test_water_focuses_healing() -> None:
    stats = stats_for_character(_character(Element.WATER), 11)
    assert stats.healing > stats.strength


def test_physical_focuses_raw_strength() -> None:
    stats = stats_for_character(_character(Element.NEUTRAL), 11)
    assert stats.strength > stats.defense
