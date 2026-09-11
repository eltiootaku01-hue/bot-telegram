from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import case, cast, Integer, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameCollection, GameProfile
from app.game.evolution import next_fusion


CAPTURE_POINTS_FIRST = 10
CAPTURE_POINTS_DUPLICATE = 10


class CollectionLike(Protocol):
    level: int
    experience: int
    evolution_stage: int
    copies: int
    rarity: str


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


def add_character_experience(*, level: int, experience: int, evolution_stage: int, gained: int, copies: int) -> ProgressionResult:
    """Pure XP progression; rank changes happen only through explicit fusion."""
    if gained < 0 or copies < 1:
        raise ValueError("Progression values cannot be negative")
    total = experience + gained
    current_level = max(1, level)
    while total >= current_level * 100:
        total -= current_level * 100
        current_level += 1
    return ProgressionResult(current_level, total, max(1, evolution_stage), False, 0)


async def apply_capture_progression(
    session: AsyncSession,
    *,
    profile_id: int,
    character_id: str,
    rarity: str,
) -> tuple[GameCollection, ProgressionResult]:
    """Apply one capture with atomic counters so simultaneous captures cannot lose copies/XP."""
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
            experience=25,
            evolution_stage=1,
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

    if not first_capture:
        total_xp = GameCollection.experience + gained
        level_up = total_xp >= GameCollection.level * 100
        await session.execute(
            update(GameCollection)
            .where(GameCollection.id == collection.id)
            .values(
                copies=GameCollection.copies + 1,
                level=case((level_up, GameCollection.level + 1), else_=GameCollection.level),
                experience=case(
                    (level_up, total_xp - (GameCollection.level * 100)),
                    else_=total_xp,
                ),
            )
        )
        await session.refresh(collection)

    profile = await session.get(GameProfile, profile_id)
    if profile is None:
        raise ValueError("Game profile disappeared during capture")

    # Keep both counters and the derived profile level inside SQL. The old
    # read/refresh/Python assignment could overwrite a newer level when two
    # captures updated the same profile concurrently.
    await session.execute(
        update(GameProfile)
        .where(GameProfile.id == profile_id)
        .values(
            experience=GameProfile.experience + gained,
            level=cast((GameProfile.experience + gained) / 500, Integer) + 1,
            updated_at=datetime.utcnow(),
        )
    )
    await session.refresh(profile)
    await session.flush()

    return collection, ProgressionResult(
        level=collection.level,
        experience=collection.experience,
        evolution_stage=collection.evolution_stage,
        evolved=False,
        points_gained=points,
    )


def capture_reward(profile: object, collection: CollectionLike) -> ProgressionResult:
    """Legacy pure helper kept for callers that do not persist concurrent state."""
    points = CAPTURE_POINTS_FIRST if collection.copies == 1 else CAPTURE_POINTS_DUPLICATE
    gained = 25 if collection.copies == 1 else 40
    result = add_character_experience(
        level=collection.level, experience=collection.experience,
        evolution_stage=collection.evolution_stage, gained=gained, copies=collection.copies,
    )
    result = ProgressionResult(result.level, result.experience, result.evolution_stage, False, points)
    collection.level = result.level
    collection.experience = result.experience
    collection.evolution_stage = result.evolution_stage
    if hasattr(profile, "experience"):
        profile.experience += gained
        profile.level = max(1, 1 + profile.experience // 500)
    return result


def collection_status(collection: CollectionLike) -> CollectionStatus:
    rule = next_fusion(collection.rarity)
    return CollectionStatus(
        next_level_at=collection.level * 100,
        evolution_copies=rule.copies_required if rule else 0,
        can_evolve=bool(rule and collection.copies >= rule.copies_required),
        next_rarity=rule.to_rarity if rule else None,
    )
