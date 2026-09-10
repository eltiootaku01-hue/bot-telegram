from dataclasses import dataclass
from enum import StrEnum


class Rarity(StrEnum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"


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
    Rarity.COMMON: 1.00,
    Rarity.RARE: 1.15,
    Rarity.EPIC: 1.35,
    Rarity.LEGENDARY: 1.60,
    Rarity.MYTHIC: 1.90,
}
