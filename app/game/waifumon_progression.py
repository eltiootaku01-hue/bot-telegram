from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.game.models import Character, Element


class WaifuMonClass(StrEnum):
    """Evolution class represented by the owned WaifuMon's level."""

    R = "R"
    S = "S"
    SR = "SR"


class CombatStyle(StrEnum):
    SPEED = "velocidad"
    DURABILITY = "dureza"
    FIRE_SPECIAL = "habilidad de fuego"
    HEALING = "curación"
    BRUTE_FORCE = "fuerza bruta"
    CONTROL = "control"
    SUPPORT = "soporte"
    CRITICAL = "golpe crítico"
    BURST = "ataque explosivo"
    PRECISION = "precisión"
    ARCANE = "poder arcano"
    BALANCED = "equilibrio"


@dataclass(frozen=True, slots=True)
class WaifuMonStats:
    """Concrete combat stats for one WaifuMon at one level."""

    level: int
    waifumon_class: WaifuMonClass
    style: CombatStyle
    max_hp: int
    strength: int
    defense: int
    speed: int
    healing: int
    special_power: int
    fire_skill: int
    critical_rate: int


@dataclass(frozen=True, slots=True)
class ClassBand:
    waifumon_class: WaifuMonClass
    min_level: int
    max_level: int
    visible_percent: str
    framing: str
    design_language: str


CLASS_BANDS: tuple[ClassBand, ...] = (
    ClassBand(
        WaifuMonClass.R,
        1,
        10,
        "20%",
        "rostro, cuello y pequeños hombros",
        "novata; diseño sencillo, silueta cerrada y presentación contenida",
    ),
    ClassBand(
        WaifuMonClass.S,
        11,
        20,
        "45%",
        "cabeza, hombros, torso y parte de la cintura",
        "evolucionada; nuevo vestuario/armadura, pose más segura y silueta más abierta",
    ),
    ClassBand(
        WaifuMonClass.SR,
        21,
        30,
        "70-80%",
        "medio cuerpo amplio hasta cintura o muslos",
        "avanzada; arte premium, pose de combate distintiva y composición narrativa",
    ),
)


ELEMENT_STYLES: dict[Element, CombatStyle] = {
    Element.WIND: CombatStyle.SPEED,
    Element.EARTH: CombatStyle.DURABILITY,
    Element.FIRE: CombatStyle.FIRE_SPECIAL,
    Element.WATER: CombatStyle.HEALING,
    Element.NEUTRAL: CombatStyle.BRUTE_FORCE,
    Element.ICE: CombatStyle.CONTROL,
    Element.LIGHT: CombatStyle.SUPPORT,
    Element.DARK: CombatStyle.CRITICAL,
    Element.LIGHTNING: CombatStyle.BURST,
    Element.MIND: CombatStyle.PRECISION,
    Element.ARCANE: CombatStyle.ARCANE,
}


# R is deliberately the weakest baseline.
# S begins above every R level and remains below SR at the same/global boundary.
CLASS_BASE: dict[WaifuMonClass, tuple[int, int, int, int, int, int, int, int]] = {
    # hp, strength, defense, speed, healing, special, fire, crit
    WaifuMonClass.R: (100, 18, 18, 18, 8, 18, 18, 5),
    WaifuMonClass.S: (160, 45, 45, 45, 20, 45, 45, 8),
    WaifuMonClass.SR: (230, 65, 65, 65, 30, 65, 65, 12),
}

CLASS_GROWTH: dict[WaifuMonClass, tuple[int, int, int, int, int, int, int, int]] = {
    WaifuMonClass.R: (5, 2, 2, 2, 1, 2, 2, 0),
    WaifuMonClass.S: (5, 2, 2, 2, 1, 2, 2, 1),
    WaifuMonClass.SR: (6, 3, 3, 3, 1, 3, 3, 1),
}


def class_band_for_level(level: int) -> ClassBand:
    if not 1 <= level <= 30:
        raise ValueError("WaifuMon level must be between 1 and 30")
    return next(band for band in CLASS_BANDS if band.min_level <= level <= band.max_level)


def waifumon_class_for_level(level: int) -> WaifuMonClass:
    return class_band_for_level(level).waifumon_class


def combat_style_for_element(element: Element) -> CombatStyle:
    return ELEMENT_STYLES[element]


def _focused_stats(
    style: CombatStyle,
    max_hp: int,
    strength: int,
    defense: int,
    speed: int,
    healing: int,
    special_power: int,
    fire_skill: int,
    critical_rate: int,
) -> tuple[int, int, int, int, int, int, int, int]:
    """Apply the chosen fighting specialty without making other stats irrelevant."""
    if style is CombatStyle.SPEED:
        speed += 12
        strength -= 2
    elif style is CombatStyle.DURABILITY:
        max_hp += 35
        defense += 12
    elif style is CombatStyle.FIRE_SPECIAL:
        special_power += 5
        fire_skill += 20
    elif style is CombatStyle.HEALING:
        healing += 30
        strength -= 2
    elif style is CombatStyle.BRUTE_FORCE:
        strength += 16
        defense += 4
    elif style is CombatStyle.CONTROL:
        speed += 4
        special_power += 12
    elif style is CombatStyle.SUPPORT:
        healing += 8
        special_power += 14
    elif style is CombatStyle.CRITICAL:
        critical_rate += 12
        speed += 3
    elif style is CombatStyle.BURST:
        speed += 6
        special_power += 10
    elif style is CombatStyle.PRECISION:
        speed += 5
        critical_rate += 7
        special_power += 5
    elif style is CombatStyle.ARCANE:
        special_power += 22
        fire_skill += 8
    return (
        max_hp,
        strength,
        defense,
        speed,
        healing,
        special_power,
        fire_skill,
        critical_rate,
    )


def stats_for_character(character: Character, level: int) -> WaifuMonStats:
    band = class_band_for_level(level)
    style = combat_style_for_element(character.element)
    base = CLASS_BASE[band.waifumon_class]
    growth = CLASS_GROWTH[band.waifumon_class]
    offset = level - band.min_level

    raw = tuple(
        base_value + growth_value * offset
        for base_value, growth_value in zip(base, growth, strict=True)
    )
    focused = _focused_stats(style, *raw)
    return WaifuMonStats(
        level=level,
        waifumon_class=band.waifumon_class,
        style=style,
        max_hp=focused[0],
        strength=focused[1],
        defense=focused[2],
        speed=focused[3],
        healing=focused[4],
        special_power=focused[5],
        fire_skill=focused[6],
        critical_rate=focused[7],
    )


def level_cap_for_class(waifumon_class: WaifuMonClass) -> int:
    return next(band.max_level for band in CLASS_BANDS if band.waifumon_class is waifumon_class)


def level_floor_for_class(waifumon_class: WaifuMonClass) -> int:
    return next(band.min_level for band in CLASS_BANDS if band.waifumon_class is waifumon_class)


def promotion_message(from_class: WaifuMonClass, to_class: WaifuMonClass) -> str:
    return (
        f"✨ Evolución WaifuMon: <b>{from_class.value}</b> → "
        f"<b>{to_class.value}</b>.\n"
        "Nuevo diseño desbloqueado y estadísticas de la nueva clase."
    )
