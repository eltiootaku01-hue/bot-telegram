from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProgressionResult:
    level: int
    experience: int
    evolution_stage: int
    evolved: bool


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
    # Copies are useful: every 3 duplicates unlock the next illustration stage.
    wanted_stage = min(4, 1 + max(0, copies - 1) // 3)
    if wanted_stage > evolution_stage:
        next_stage = wanted_stage
        evolved = True

    return ProgressionResult(current_level, total, next_stage, evolved)
