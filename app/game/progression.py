from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Protocol

from sqlalchemy import Integer, case, cast, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import GameCollection, GameProfile
from app.game.evolution import next_fusion
from app.game.models import Character, Element, Rarity


CAPTURE_POINTS_FIRST = 10
CAPTURE_POINTS_DUPLICATE = 10
MAX_WAIFUMON_LEVEL = 30


class EvolutionStage(IntEnum):
    """Base form plus three level-based evolutions."""

    BASE = 1
    EVOLUTION_1 = 2
    EVOLUTION_2 = 3
    EVOLUTION_3 = 4


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


class CollectionLike(Protocol):
    level: int
    experience: int
    evolution_stage: int
    copies: int
    rarity: str
    potential_seed: str | None


@dataclass(frozen=True, slots=True)
class ProgressionResult:
    level: int
    experience: int
    evolution_stage: int
    evolved: bool
    points_gained: int


@dataclass(frozen=True, slots=True)
class CollectionStatus:
    next_level_at: int
    evolution_copies: int
    can_evolve: bool
    next_rarity: str | None


@dataclass(frozen=True, slots=True)
class EvolutionBand:
    stage: EvolutionStage
    min_level: int
    max_level: int
    art_visibility: str
    framing: str
    design_language: str


EVOLUTION_BANDS: tuple[EvolutionBand, ...] = (
    EvolutionBand(EvolutionStage.BASE, 1, 5, "15%", "rostro y hombros", "forma base"),
    EvolutionBand(
        EvolutionStage.EVOLUTION_1,
        6,
        10,
        "30%",
        "cabeza, hombros y torso",
        "primera evolución; silueta y pose renovadas",
    ),
    EvolutionBand(
        EvolutionStage.EVOLUTION_2,
        11,
        20,
        "60%",
        "medio cuerpo hasta cintura",
        "segunda evolución; vestuario y presencia de combate ampliados",
    ),
    EvolutionBand(
        EvolutionStage.EVOLUTION_3,
        21,
        30,
        "100%",
        "cuerpo completo",
        "tercera evolución; arte final y composición completa",
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


# Combat class is the WaifuMon rarity D..SSS. It is independent from level.
RARITY_STAT_SCALE: dict[Rarity, float] = {
    Rarity.D: 0.78,
    Rarity.C: 0.92,
    Rarity.B: 1.10,
    Rarity.A: 1.35,
    Rarity.S: 1.68,
    Rarity.SS: 2.08,
    Rarity.SSS: 2.55,
}


@dataclass(frozen=True, slots=True)
class WaifuMonStats:
    """True combat stats resolved from class, level and hidden individual potential."""

    level: int
    rarity: Rarity
    evolution_stage: EvolutionStage
    style: CombatStyle
    potential_score: int
    max_hp: int
    strength: int
    defense: int
    speed: int
    healing: int
    special_power: int
    fire_skill: int
    critical_rate: int


def evolution_band_for_level(level: int) -> EvolutionBand:
    if not 1 <= level <= MAX_WAIFUMON_LEVEL:
        raise ValueError("WaifuMon level must be between 1 and 30")
    return next(band for band in EVOLUTION_BANDS if band.min_level <= level <= band.max_level)


def evolution_stage_for_level(level: int) -> EvolutionStage:
    return evolution_band_for_level(level).stage


def evolution_next_level(stage: EvolutionStage) -> int | None:
    if stage is EvolutionStage.BASE:
        return 6
    if stage is EvolutionStage.EVOLUTION_1:
        return 11
    if stage is EvolutionStage.EVOLUTION_2:
        return 21
    return None


def level_cap_for_evolution_stage(stage: EvolutionStage) -> int:
    return next(band.max_level for band in EVOLUTION_BANDS if band.stage is stage)


def level_floor_for_evolution_stage(stage: EvolutionStage) -> int:
    return next(band.min_level for band in EVOLUTION_BANDS if band.stage is stage)


def combat_style_for_element(element: Element) -> CombatStyle:
    return ELEMENT_STYLES[element]


def promotion_message(from_stage: EvolutionStage, to_stage: EvolutionStage) -> str:
    return (
        f"✨ <b>Evolución de nivel WaifuMon</b>: "
        f"etapa {from_stage.value} → <b>etapa {to_stage.value}</b>.\n"
        "Nuevo arte desbloqueado y crecimiento de estadísticas."
    )


def _digest(seed: str) -> bytes:
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _variation(seed: str, stat_name: str) -> float:
    digest = _digest(f"{seed}:{stat_name}")
    return -0.08 + (digest[0] / 255.0) * 0.16


def potential_score_for_seed(seed: str) -> int:
    digest = _digest(f"{seed}:potential")
    return 1 + (digest[0] * 100 // 256)


def _base_stats(
    character: Character,
    rarity: Rarity,
) -> tuple[int, int, int, int, int, int, int, int]:
    foundation = 45 + round(character.power_score * 0.55)
    rarity_scale = RARITY_STAT_SCALE[rarity]
    return (
        round(foundation * 2.20 * rarity_scale),
        round(foundation * 0.55 * rarity_scale),
        round(foundation * 0.50 * rarity_scale),
        round(foundation * 0.50 * rarity_scale),
        round((10 + foundation * 0.16) * rarity_scale),
        round(foundation * 0.60 * rarity_scale),
        round(foundation * 0.55 * rarity_scale),
        max(1, round((4 + foundation * 0.04) * (0.8 + 0.2 * rarity_scale))),
    )


def _apply_style(
    style: CombatStyle,
    values: tuple[int, int, int, int, int, int, int, int],
) -> tuple[int, int, int, int, int, int, int, int]:
    max_hp, strength, defense, speed, healing, special, fire, critical = values
    if style is CombatStyle.SPEED:
        speed += 12
        strength = max(1, strength - 2)
    elif style is CombatStyle.DURABILITY:
        max_hp += 35
        defense += 12
    elif style is CombatStyle.FIRE_SPECIAL:
        special += 5
        fire += 20
    elif style is CombatStyle.HEALING:
        healing += 30
        strength = max(1, strength - 2)
    elif style is CombatStyle.BRUTE_FORCE:
        strength += 16
        defense += 4
    elif style is CombatStyle.CONTROL:
        speed += 4
        special += 12
    elif style is CombatStyle.SUPPORT:
        healing += 8
        special += 14
    elif style is CombatStyle.CRITICAL:
        critical += 12
        speed += 3
    elif style is CombatStyle.BURST:
        speed += 6
        special += 10
    elif style is CombatStyle.PRECISION:
        speed += 5
        critical += 7
        special += 5
    elif style is CombatStyle.ARCANE:
        special += 22
        fire += 8
    return max_hp, strength, defense, speed, healing, special, fire, critical


def stats_for_character(
    character: Character,
    level: int,
    *,
    rarity: Rarity | str | None = None,
    potential_seed: str | None = None,
) -> WaifuMonStats:
    """Resolve stats for preview or gameplay without persisting anything."""
    if not 1 <= level <= MAX_WAIFUMON_LEVEL:
        raise ValueError("WaifuMon level must be between 1 and 30")

    resolved_rarity = (
        rarity
        if isinstance(rarity, Rarity)
        else Rarity(rarity or character.rarity.value)
    )
    seed = potential_seed or "preview-neutral"
    stage = evolution_stage_for_level(level)
    style = combat_style_for_element(character.element)

    values = _base_stats(character, resolved_rarity)
    level_factor = 1.0 + (level - 1) * 0.038
    values = tuple(round(value * level_factor) for value in values)

    names = ("max_hp", "strength", "defense", "speed", "healing", "special", "fire", "critical")
    values = tuple(
        max(1, round(value * (1.0 + _variation(seed, name))))
        for value, name in zip(values, names, strict=True)
    )
    values = _apply_style(style, values)

    return WaifuMonStats(
        level=level,
        rarity=resolved_rarity,
        evolution_stage=stage,
        style=style,
        potential_score=potential_score_for_seed(seed),
        max_hp=values[0],
        strength=values[1],
        defense=values[2],
        speed=values[3],
        healing=values[4],
        special_power=values[5],
        fire_skill=values[6],
        critical_rate=min(95, values[7]),
    )


def stats_for_collection(character: Character, collection: CollectionLike) -> WaifuMonStats:
    """Resolve the real owned stats using the persisted individual seed."""
    return stats_for_character(
        character,
        collection.level,
        rarity=Rarity(collection.rarity),
        potential_seed=collection.potential_seed or f"legacy:{collection.character_id}",
    )


def add_collection_experience(
    *,
    level: int,
    experience: int,
    evolution_stage: int,
    gained: int,
    copies: int,
) -> ProgressionResult:
    return add_character_experience(
        level=level,
        experience=experience,
        evolution_stage=evolution_stage,
        gained=gained,
        copies=copies,
    )


def add_character_experience(
    *,
    level: int,
    experience: int,
    evolution_stage: int,
    gained: int,
    copies: int,
) -> ProgressionResult:
    """Pure level progression; XP never promotes rarity/class."""
    if gained < 0 or copies < 1:
        raise ValueError("Progression values cannot be negative")
    old_stage = evolution_stage_for_level(max(1, min(MAX_WAIFUMON_LEVEL, level)))
    current_level = min(MAX_WAIFUMON_LEVEL, max(1, level))
    total = max(0, experience) + gained

    while current_level < MAX_WAIFUMON_LEVEL and total >= current_level * 100:
        total -= current_level * 100
        current_level += 1

    if current_level >= MAX_WAIFUMON_LEVEL:
        current_level = MAX_WAIFUMON_LEVEL
        total = 0

    new_stage = evolution_stage_for_level(current_level)
    return ProgressionResult(
        current_level,
        total,
        new_stage.value,
        new_stage is not old_stage,
        0,
    )


async def apply_capture_progression(
    session: AsyncSession,
    *,
    profile_id: int,
    character_id: str,
    rarity: str,
    potential_seed: str | None = None,
) -> tuple[GameCollection, ProgressionResult]:
    """Apply one capture while keeping rarity and level as independent axes."""
    collection = await session.scalar(
        select(GameCollection).where(
            GameCollection.profile_id == profile_id,
            GameCollection.character_id == character_id,
        )
    )

    first_capture = collection is None
    if first_capture:
        collection = GameCollection(
            profile_id=profile_id,
            character_id=character_id,
            rarity=rarity,
            level=1,
            copies=1,
            experience=0,
            evolution_stage=EvolutionStage.BASE.value,
            potential_seed=potential_seed or secrets.token_hex(16),
        )
        try:
            async with session.begin_nested():
                session.add(collection)
                await session.flush()
        except IntegrityError:
            collection = await session.scalar(
                select(GameCollection).where(
                    GameCollection.profile_id == profile_id,
                    GameCollection.character_id == character_id,
                )
            )
            if collection is None:
                raise
            first_capture = False

    gained = 25 if first_capture else 40
    points = CAPTURE_POINTS_FIRST if first_capture else CAPTURE_POINTS_DUPLICATE

    if first_capture:
        result = add_character_experience(
            level=collection.level,
            experience=collection.experience,
            evolution_stage=collection.evolution_stage,
            gained=gained,
            copies=collection.copies,
        )
        collection.level = result.level
        collection.experience = result.experience
        collection.evolution_stage = result.evolution_stage
        await session.flush()

    if not first_capture:
        result = add_character_experience(
            level=collection.level,
            experience=collection.experience,
            evolution_stage=collection.evolution_stage,
            gained=gained,
            copies=collection.copies + 1,
        )
        claimed = await session.execute(
            update(GameCollection)
            .where(
                GameCollection.id == collection.id,
                GameCollection.copies >= 1,
            )
            .values(
                copies=GameCollection.copies + 1,
                level=result.level,
                experience=result.experience,
                evolution_stage=result.evolution_stage,
            )
        )
        if claimed.rowcount != 1:
            raise RuntimeError("WaifuMon collection changed during capture")
        await session.refresh(collection)

    profile = await session.get(GameProfile, profile_id)
    if profile is None:
        raise ValueError("Game profile disappeared during capture")

    await session.execute(
        update(GameProfile)
        .where(GameProfile.id == profile_id)
        .values(
            experience=GameProfile.experience + gained,
            level=case(
                (GameProfile.experience + gained >= 12000, 25),
                else_=cast((GameProfile.experience + gained) / 500, Integer) + 1,
            ),
            updated_at=utc_now(),
        )
    )
    await session.refresh(profile)

    return collection, ProgressionResult(
        level=collection.level,
        experience=collection.experience,
        evolution_stage=collection.evolution_stage,
        evolved=not first_capture and collection.evolution_stage != 1,
        points_gained=points,
    )


def capture_reward(profile: object, collection: CollectionLike) -> ProgressionResult:
    """Legacy pure helper using the same level-only progression contract."""
    gained = 25 if collection.copies == 1 else 40
    points = CAPTURE_POINTS_FIRST if collection.copies == 1 else CAPTURE_POINTS_DUPLICATE
    before_stage = collection.evolution_stage
    result = add_character_experience(
        level=collection.level,
        experience=collection.experience,
        evolution_stage=collection.evolution_stage,
        gained=gained,
        copies=collection.copies,
    )
    collection.level = result.level
    collection.experience = result.experience
    collection.evolution_stage = result.evolution_stage
    if hasattr(profile, "experience"):
        profile.experience += gained
        profile.level = max(1, 1 + profile.experience // 500)
    return ProgressionResult(
        result.level,
        result.experience,
        result.evolution_stage,
        result.evolution_stage != before_stage,
        points,
    )


def collection_status(collection: CollectionLike) -> CollectionStatus:
    rule = next_fusion(collection.rarity)
    next_level = collection.level * 100 if collection.level < MAX_WAIFUMON_LEVEL else 0
    return CollectionStatus(
        next_level_at=next_level,
        evolution_copies=rule.copies_required if rule else 0,
        can_evolve=bool(rule and collection.copies >= rule.copies_required),
        next_rarity=rule.to_rarity if rule else None,
    )
