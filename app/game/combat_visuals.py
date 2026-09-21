from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


SPRITE_SIZE = 128
SPRITE_EXTENSION = ".png"
SPRITE_VARIANTS = ("idle", "attack", "hit")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class CombatSpriteVariant(StrEnum):
    IDLE = "idle"
    ATTACK = "attack"
    HIT = "hit"


@dataclass(frozen=True, slots=True)
class CombatVisualContract:
    """Presentation-only contract for the lightweight 2D combat frontend."""

    sprite_width: int = SPRITE_SIZE
    sprite_height: int = SPRITE_SIZE
    transparent_background: bool = True
    cut_in_duration_ms: int = 1500


@dataclass(frozen=True, slots=True)
class CombatSpriteValidation:
    valid: bool
    width: int | None
    height: int | None
    transparent: bool | None
    size_bytes: int
    reason: str


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


def png_metadata(path: Path) -> tuple[int, int, bool] | None:
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != PNG_SIGNATURE:
        return None
    if data[12:16] != b"IHDR":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    color_type = data[25]
    # PNG color type 4 (gray+alpha) and 6 (RGBA) carry an alpha channel.
    transparent = color_type in {4, 6}
    return width, height, transparent


def validate_combat_sprite_asset(path: Path) -> CombatSpriteValidation:
    if not path.is_file():
        return CombatSpriteValidation(False, None, None, None, 0, "file does not exist")
    size = path.stat().st_size
    if path.suffix.casefold() != SPRITE_EXTENSION:
        return CombatSpriteValidation(False, None, None, None, size, "asset must be PNG")
    metadata = png_metadata(path)
    if metadata is None:
        return CombatSpriteValidation(False, None, None, None, size, "invalid PNG")
    width, height, transparent = metadata
    if (width, height) != (SPRITE_SIZE, SPRITE_SIZE):
        return CombatSpriteValidation(
            False,
            width,
            height,
            transparent,
            size,
            f"expected {SPRITE_SIZE}x{SPRITE_SIZE}, got {width}x{height}",
        )
    if not transparent:
        return CombatSpriteValidation(
            False, width, height, False, size, "sprite must provide an alpha channel"
        )
    return CombatSpriteValidation(True, width, height, True, size, "ok")


def validate_combat_result_for_animation(result: dict) -> str:
    """Map an engine result to an animation intent without recalculating rules."""
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
