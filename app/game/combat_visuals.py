from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


SPRITE_SIZE = 128
SPRITE_EXTENSION = ".png"
SPRITE_VARIANTS = ("idle", "attack", "hit")


class CombatSpriteVariant(StrEnum):
    IDLE = "idle"
    ATTACK = "attack"
    HIT = "hit"


@dataclass(frozen=True, slots=True)
class CombatVisualContract:
    """Presentation-only contract for the lightweight 2D combat frontend.

    This module never calculates damage, HP, accuracy, elemental multipliers,
    turn order, or any other gameplay rule. Those remain authoritative in Java.
    """

    sprite_width: int = SPRITE_SIZE
    sprite_height: int = SPRITE_SIZE
    transparent_background: bool = True
    cut_in_duration_ms: int = 1500


def combat_sprite_path(
    character_id: str,
    variant: CombatSpriteVariant | str = CombatSpriteVariant.IDLE,
) -> str:
    safe_id = character_id.strip()
    if not safe_id or "/" in safe_id or "\\" in safe_id:
        raise ValueError("character_id must be a safe asset identifier")

    resolved = (
        variant
        if isinstance(variant, CombatSpriteVariant)
        else CombatSpriteVariant(variant.strip().casefold())
    )
    return f"assets/production/sprites/{safe_id}_{resolved.value}{SPRITE_EXTENSION}"


def validate_combat_result_for_animation(result: dict) -> str:
    """Map an engine result to an animation intent without recomputing rules."""
    if not result.get("success"):
        return "error"
    payload = result.get("payload") or {}
    action = payload.get("action")
    if action == "special":
        return "special_cut_in"
    if action == "attack":
        return "attack"
    if action == "defend":
        return "idle"
    return "idle"


COMBAT_VISUAL_CONTRACT = CombatVisualContract()
