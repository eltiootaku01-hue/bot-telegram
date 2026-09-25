from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from functools import lru_cache
from typing import Protocol

from sqlalchemy import Integer, case, cast, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import GameCollection, GameProfile
from app.game.evolution import next_fusion
from app.game.java_engine import WaifuMonJavaEngine, default_java_engine
from app.game.models import Character, Rarity


CAPTURE_POINTS_FIRST = 10
CAPTURE_POINTS_DUPLICATE = 10
MAX_WAIFUMON_LEVEL = 30


class EvolutionStage(IntEnum):
    """Three visual stages derived only from the collection level."""

    BASE = 1
    EVOLUTION_1 = 2
    EVOLUTION_2 = 3


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
    character_id: str
    level: int
    experience: int
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
    EvolutionBand(
        EvolutionStage.BASE,
        1,
        10,
        "30%",
        "rostro, hombros y torso",
        "etapa 1; forma inicial completamente definida",
    ),
    EvolutionBand(
        EvolutionStage.EVOLUTION_1,
        11,
        20,
        "60%",
        "medio cuerpo hasta cintura",
        "etapa 2; vestuario y presencia de combate ampliados",
    ),
    EvolutionBand(
        EvolutionStage.EVOLUTION_2,
        21,
        30,
        "100%",
        "cuerpo completo",
        "etapa 3; forma final y composición completa",
    ),
)


@dataclass(frozen=True, slots=True)
class WaifuMonStats:
    """True combat stats resolved by the Java gameplay authority."""

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


@lru_cache(maxsize=1)
def _java_rules() -> WaifuMonJavaEngine:
    return default_java_engine()


def evolution_stage_for_level(level: int) -> EvolutionStage:
    """Return the visual stage as a pure function of level."""
    if not 1 <= level <= MAX_WAIFUMON_LEVEL:
        raise ValueError("WaifuMon level must be between 1 and 30")
    if level <= 10:
        return EvolutionStage.BASE
    if level <= 20:
        return EvolutionStage.EVOLUTION_1
    return EvolutionStage.EVOLUTION_2


def evolution_band_for_level(level: int) -> EvolutionBand:
    stage = evolution_stage_for_level(level)
    return next(band for band in EVOLUTION_BANDS if band.stage is stage)


def evolution_next_level(stage: EvolutionStage) -> int | None:
    if not isinstance(stage, EvolutionStage):
        stage = EvolutionStage(stage)
    return {
        EvolutionStage.BASE: 11,
        EvolutionStage.EVOLUTION_1: 21,
        EvolutionStage.EVOLUTION_2: None,
    }[stage]


def level_cap_for_evolution_stage(stage: EvolutionStage) -> int:
    return evolution_band_for_level(level_floor_for_evolution_stage(stage)).max_level


def level_floor_for_evolution_stage(stage: EvolutionStage) -> int:
    if not isinstance(stage, EvolutionStage):
        stage = EvolutionStage(stage)
    return {
        EvolutionStage.BASE: 1,
        EvolutionStage.EVOLUTION_1: 11,
        EvolutionStage.EVOLUTION_2: 21,
    }[stage]


def promotion_message(from_stage: EvolutionStage, to_stage: EvolutionStage) -> str:
    return (
        f"✨ <b>Evolución de nivel WaifuMon</b>: "
        f"etapa {from_stage.value} → <b>etapa {to_stage.value}</b>.\n"
        "Nuevo arte desbloqueado y crecimiento de estadísticas."
    )


def potential_score_for_seed(seed: str) -> int:
    if not seed.strip():
        raise ValueError("potential seed must not be empty")
    return _java_rules().potential_score(seed=seed)


def combat_style_for_element(element: object) -> CombatStyle:
    """Resolve the element specialty through the authoritative Java engine."""
    value = getattr(element, "value", element)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("element must be a non-empty string")
    return CombatStyle(_java_rules().style(element=value))


def stats_for_character(
    character: Character,
    level: int,
    *,
    rarity: Rarity | str | None = None,
    potential_seed: str | None = None,
) -> WaifuMonStats:
    """Resolve stats through Java without persisting state."""
    resolved_rarity = (
        rarity if isinstance(rarity, Rarity) else Rarity(rarity or character.rarity.value)
    )
    result = _java_rules().stats(
        character={
            "id": character.id,
            "name": character.name,
            "element_type": character.element.value,
            "power_score": character.power_score,
        },
        level=level,
        rarity=resolved_rarity.value,
        potential_seed=potential_seed or "preview-neutral",
    )
    return WaifuMonStats(
        level=int(result["level"]),
        rarity=Rarity(result["rarity"]),
        evolution_stage=evolution_stage_for_level(int(result["level"])),
        style=CombatStyle(result["style"]),
        potential_score=int(result["potential_score"]),
        max_hp=int(result["max_hp"]),
        strength=int(result["strength"]),
        defense=int(result["defense"]),
        speed=int(result["speed"]),
        healing=int(result["healing"]),
        special_power=int(result["special_power"]),
        fire_skill=int(result["fire_skill"]),
        critical_rate=int(result["critical_rate"]),
    )


def stats_for_collection(character: Character, collection: CollectionLike) -> WaifuMonStats:
    """Resolve owned stats from the persisted individual potential seed."""
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
    gained: int,
    copies: int,
) -> ProgressionResult:
    return add_character_experience(
        level=level,
        experience=experience,
        gained=gained,
        copies=copies,
    )


def add_character_experience(
    *,
    level: int,
    experience: int,
    gained: int,
    copies: int,
) -> ProgressionResult:
    """Resolve XP/level through Java; stage remains a pure function of level."""
    if not 1 <= level <= MAX_WAIFUMON_LEVEL:
        raise ValueError("WaifuMon level must be between 1 and 30")
    before_stage = evolution_stage_for_level(level)
    result = _java_rules().progression(
        level=level,
        experience=experience,
        gained=gained,
        copies=copies,
    )
    new_level = int(result["level"])
    new_stage = evolution_stage_for_level(new_level)
    return ProgressionResult(
        level=new_level,
        experience=int(result["experience"]),
        evolution_stage=new_stage,
        evolved=new_stage is not before_stage,
        points_gained=0,
    )


async def apply_capture_progression(
    session: AsyncSession,
    *,
    profile_id: int,
    character_id: str,
    rarity: str,
    potential_seed: str | None = None,
    user_id: int | None = None,
    chat_id: int | None = None,
) -> tuple[GameCollection, ProgressionResult]:
    """Apply one capture while keeping rarity and level as independent axes."""
    del user_id, chat_id

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
            gained=gained,
            copies=collection.copies,
        )
        collection.level = result.level
        collection.experience = result.experience
        await session.flush()

    if not first_capture:
        result = add_character_experience(
            level=collection.level,
            experience=collection.experience,
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
        evolution_stage=evolution_stage_for_level(collection.level),
        evolved=not first_capture and result.evolved,
        points_gained=points,
    )


def capture_reward(profile: object, collection: CollectionLike) -> ProgressionResult:
    """Legacy helper that delegates level progression to Java."""
    gained = 25 if collection.copies == 1 else 40
    points = CAPTURE_POINTS_FIRST if collection.copies == 1 else CAPTURE_POINTS_DUPLICATE
    before_stage = evolution_stage_for_level(collection.level)
    result = add_character_experience(
        level=collection.level,
        experience=collection.experience,
        gained=gained,
        copies=collection.copies,
    )
    collection.level = result.level
    collection.experience = result.experience
    if hasattr(profile, "experience"):
        profile.experience += gained
        profile.level = max(1, 1 + profile.experience // 500)
    return ProgressionResult(
        result.level,
        result.experience,
        evolution_stage_for_level(collection.level),
        evolution_stage_for_level(collection.level) is not before_stage,
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
