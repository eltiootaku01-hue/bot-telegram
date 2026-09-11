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
    Rarity.D: 1.00,
    Rarity.C: 1.10,
    Rarity.B: 1.25,
    Rarity.A: 1.50,
    Rarity.S: 1.80,
    Rarity.SS: 2.20,
    Rarity.SSS: 2.60,
}
