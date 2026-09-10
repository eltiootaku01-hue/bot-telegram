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

    # 1st form is the base card. Copies 4, 7 and 10 unlock forms 2, 3 and 4.
    wanted_stage = min(4, 1 + max(0, copies - 1) // 3)
    evolved = wanted_stage > evolution_stage
    return ProgressionResult(
        level=current_level,
        experience=total,
        evolution_stage=max(evolution_stage, wanted_stage),
        evolved=evolved,
    )


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
    if hasattr(profile, "experience"):
        profile.experience += gained
        profile.level = max(1, 1 + profile.experience // 500)
    return result


def collection_status(collection: CollectionLike) -> CollectionStatus:
    required_copies = 1 + collection.evolution_stage * 3
    return CollectionStatus(
        next_level_at=collection.level * 100,
        evolution_copies=required_copies,
        can_evolve=collection.copies >= required_copies and collection.evolution_stage < 4,
    )
