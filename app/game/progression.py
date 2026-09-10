from dataclasses import dataclass
from typing import Protocol


class CollectionLike(Protocol):
    level: int
    experience: int
    evolution_stage: int
    copies: int


@dataclass(frozen=True, slots=True)
class ProgressionResult:
    level: int
    experience: int
    evolution_stage: int
    evolved: bool


@dataclass(frozen=True, slots=True)
class CollectionStatus:
    next_level_at: int
    evolution_copies: int
    can_evolve: bool


def add_character_experience(
    *,
    level: int,
    experience: int,
    evolution_stage: int,
    gained: int,
    copies: int,
) -> ProgressionResult:
    """Pure progression rules; DB persistence stays in the game service/module."""
    if gained < 0 or copies < 1:
        raise ValueError("Progression values cannot be negative")

    total = experience + gained
    current_level = max(1, level)
    while total >= current_level * 100:
        total -= current_level * 100
        current_level += 1

    next_stage = evolution_stage
    evolved = False
    # Copies have a concrete purpose: each 3 total copies unlocks a new art stage.
    wanted_stage = min(4, 1 + max(0, copies - 1) // 3)
    if wanted_stage > evolution_stage:
        next_stage = wanted_stage
        evolved = True

    return ProgressionResult(current_level, total, next_stage, evolved)


def capture_reward(profile: object, collection: CollectionLike) -> ProgressionResult:
    """Apply the deterministic reward from a successful wild capture."""
    gained = 25 if collection.copies == 1 else 40
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
    # Player-level progression is intentionally modest and deterministic.
    if hasattr(profile, "experience"):
        profile.experience += gained
        profile.level = max(1, 1 + profile.experience // 500)
    return result


def collection_status(collection: CollectionLike) -> CollectionStatus:
    required_copies = min(4, 1 + collection.evolution_stage * 3)
    return CollectionStatus(
        next_level_at=collection.level * 100,
        evolution_copies=required_copies,
        can_evolve=collection.copies >= required_copies and collection.evolution_stage < 4,
    )
