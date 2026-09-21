from dataclasses import dataclass
from enum import StrEnum


class Rarity(StrEnum):
    D = "D"
    C = "C"
    B = "B"
    A = "A"
    S = "S"
    SS = "SS"
    SSS = "SSS"


class CardTier(StrEnum):
    R = "R"
    S = "S"
    SR = "SR"
    UR = "UR"


class Element(StrEnum):
    FIRE = "fuego"
    WATER = "agua"
    EARTH = "tierra"
    WIND = "aire"
    ICE = "hielo"
    LIGHT = "luz"
    DARK = "oscuridad"
    LIGHTNING = "rayo"
    MIND = "mente"
    ARCANE = "arcano"
    NEUTRAL = "neutro"


def rarity_from_power(power_score: int) -> Rarity:
    """Translate the game's 0..100 power axis into the existing drop ladder."""
    if not 0 <= power_score <= 100:
        raise ValueError("power_score must be between 0 and 100")
    if power_score >= 95:
        return Rarity.SSS
    if power_score >= 85:
        return Rarity.SS
    if power_score >= 75:
        return Rarity.S
    if power_score >= 60:
        return Rarity.A
    if power_score >= 45:
        return Rarity.B
    if power_score >= 30:
        return Rarity.C
    return Rarity.D


def card_tier_from_scores(popularity_score: int, power_score: int) -> CardTier:
    """Derive the four presentation classes from the two independent game axes."""
    if not 0 <= popularity_score <= 100:
        raise ValueError("popularity_score must be between 0 and 100")
    if not 0 <= power_score <= 100:
        raise ValueError("power_score must be between 0 and 100")
    combined = (popularity_score + power_score) / 2
    if combined >= 78:
        return CardTier.UR
    if combined >= 52:
        return CardTier.SR
    if combined >= 40:
        return CardTier.S
    return CardTier.R


@dataclass(frozen=True, slots=True)
class Character:
    id: str
    name: str
    anime: str
    rarity: Rarity
    level: int = 1
    attack_name: str = "Ataque básico"
    defense_name: str = "Defensa improvisada"
    special_name: str = "Ataque especial"
    popularity_score: int = 50
    power_score: int = 50
    element: Element = Element.NEUTRAL
    card_tier: CardTier | None = None
    popularity_rank: int | None = None
    popularity_source: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.popularity_score <= 100:
            raise ValueError("popularity_score must be between 0 and 100")
        if not 0 <= self.power_score <= 100:
            raise ValueError("power_score must be between 0 and 100")
        if self.level < 1:
            raise ValueError("character level must be positive")
        if self.popularity_rank is not None and self.popularity_rank < 1:
            raise ValueError("popularity_rank must be positive")
        expected = card_tier_from_scores(self.popularity_score, self.power_score)
        if self.card_tier is None:
            object.__setattr__(self, "card_tier", expected)
        elif self.card_tier is not expected:
            raise ValueError(
                f"card_tier {self.card_tier} does not match popularity/power scores; expected {expected}"
            )


@dataclass(frozen=True, slots=True)
class CombatAction:
    key: str
    label: str
    power: int


@dataclass(frozen=True, slots=True)
class Combatant:
    character: Character
    hp: int
    max_hp: int


@dataclass(frozen=True, slots=True)
class CombatResult:
    attacker: str
    defender: str
    damage: int
    action: CombatAction
    critical: bool
    defender_hp: int


RARITY_MULTIPLIER: dict[Rarity, float] = {
    Rarity.D: 1.00,
    Rarity.C: 1.10,
    Rarity.B: 1.25,
    Rarity.A: 1.50,
    Rarity.S: 1.80,
    Rarity.SS: 2.20,
    Rarity.SSS: 2.60,
}
