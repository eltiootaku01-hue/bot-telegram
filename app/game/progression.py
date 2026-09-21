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
    character_id: str
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


def evolution_band_for_level(level: int) -> EvolutionBand:
    result = _java_rules().evolution(level=level)
    stage = EvolutionStage(int(result["evolution_stage"]))
    metadata = {
        EvolutionStage.BASE: ("15%", "rostro y hombros", "forma base"),
        EvolutionStage.EVOLUTION_1: (
            "30%",
            "cabeza, hombros y torso",
            "primera evolución; silueta y pose renovadas",
        ),
        EvolutionStage.EVOLUTION_2: (
            "60%",
            "medio cuerpo hasta cintura",
            "segunda evolución; vestuario y presencia de combate ampliados",
        ),
        EvolutionStage.EVOLUTION_3: (
            "100%",
            "cuerpo completo",
            "tercera evolución; arte final y composición completa",
        ),
    }
    art_visibility, framing, design_language = metadata[stage]
    return EvolutionBand(
        stage=stage,
        min_level=int(result["min_level"]),
        max_level=int(result["max_level"]),
        art_visibility=art_visibility,
        framing=framing,
        design_language=design_language,
    )


def evolution_stage_for_level(level: int) -> EvolutionStage:
    return evolution_band_for_level(level).stage


def evolution_next_level(stage: EvolutionStage) -> int | None:
    result = _java_rules().evolution(level=level_floor_for_evolution_stage(stage))
    next_level = int(result["next_level"])
    return next_level or None


def level_cap_for_evolution_stage(stage: EvolutionStage) -> int:
    return evolution_band_for_level(level_floor_for_evolution_stage(stage)).max_level


def level_floor_for_evolution_stage(stage: EvolutionStage) -> int:
    if not isinstance(stage, EvolutionStage):
        stage = EvolutionStage(stage)
    return {
        EvolutionStage.BASE: 1,
        EvolutionStage.EVOLUTION_1: 6,
        EvolutionStage.EVOLUTION_2: 11,
        EvolutionStage.EVOLUTION_3: 21,
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
            "element": character.element.value,
            "power_score": character.power_score,
        },
        level=level,
        rarity=resolved_rarity.value,
        potential_seed=potential_seed or "preview-neutral",
    )
    return WaifuMonStats(
        level=int(result["level"]),
        rarity=Rarity(result["rarity"]),
        evolution_stage=EvolutionStage(int(result["evolution_stage"])),
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
    """Resolve level/XP progression in Java; Python only maps the DTO."""
    result = _java_rules().progression(
        level=level,
        experience=experience,
        evolution_stage=evolution_stage,
        gained=gained,
        copies=copies,
    )
    return ProgressionResult(
        level=int(result["level"]),
        experience=int(result["experience"]),
        evolution_stage=int(result["evolution_stage"]),
        evolved=bool(result["evolved"]),
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
    """Legacy helper that delegates level progression to Java."""
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
