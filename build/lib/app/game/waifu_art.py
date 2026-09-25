from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from app.game.card_art_assets import CARD_ART_EXTENSION, card_asset_path
from app.game.catalog import CHARACTERS
from app.game.waifumon_progression import evolution_stage_for_level

PRODUCTION_ART_ROOT = PurePosixPath("assets", "production", "cards")


@dataclass(frozen=True, slots=True)
class WaifuArt:
    character_id: str
    repository_path: str


def _production_path(filename: str) -> str:
    return str(PRODUCTION_ART_ROOT / filename)


def art_path_for(character_id: str) -> str:
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    return card_asset_path(character_id, "normal")


def art_candidates_for(character_id: str) -> tuple[str, ...]:
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    return (art_path_for(character_id),)


def declared_art(character_id: str) -> WaifuArt:
    return WaifuArt(character_id=character_id, repository_path=art_path_for(character_id))


def declared_art_for_catalog() -> tuple[WaifuArt, ...]:
    return tuple(declared_art(character_id) for character_id in sorted(CHARACTERS))


def rarity_art_candidates_for(character_id: str, rarity: str) -> tuple[str, ...]:
    """Return the only production JPEG path for a combat-rarity artwork."""
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    safe_rarity = rarity.upper()
    if safe_rarity not in {"D", "C", "B", "A", "S", "SS", "SSS"}:
        raise ValueError("rarity must be D, C, B, A, S, SS or SSS")
    return (
        _production_path(
            f"{character_id}--class-{safe_rarity.casefold()}{CARD_ART_EXTENSION}"
        ),
    )


def variant_art_candidates_for(character_id: str, variant: str) -> tuple[str, ...]:
    """Return the only production JPEG path for a normal/shiny card variant."""
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    safe_variant = variant.casefold()
    if safe_variant not in {"normal", "shiny"}:
        raise ValueError("variant must be normal or shiny")
    return (card_asset_path(character_id, safe_variant),)


def evolution_art_candidates_for(character_id: str, level: int) -> tuple[str, ...]:
    """Return the only production JPEG path for the level-derived visual stage."""
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    stage = evolution_stage_for_level(level).value
    return (_production_path(f"{character_id}--stage{stage}.jpg"),)
