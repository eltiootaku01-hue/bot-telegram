from dataclasses import dataclass
from typing import Protocol

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


def capture_reward(profile: object, collection: CollectionLike) -> ProgressionResult:
    """Apply deterministic XP/point progression after a successful capture."""
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
