from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from app.game.catalog import CHARACTERS

RUNTIME_ART_SUFFIXES = (".png", ".webp", ".jpg", ".jpeg")


@dataclass(frozen=True, slots=True)
class WaifuArt:
    character_id: str
    repository_path: str


def art_path_for(character_id: str) -> str:
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    return str(PurePosixPath("assets", "waifus", character_id + ".png"))


def art_candidates_for(character_id: str) -> tuple[str, ...]:
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    root = PurePosixPath("assets", "waifus")
    return tuple(str(root / f"{character_id}{suffix}") for suffix in RUNTIME_ART_SUFFIXES)


def declared_art(character_id: str) -> WaifuArt:
    return WaifuArt(character_id=character_id, repository_path=art_path_for(character_id))


def declared_art_for_catalog() -> tuple[WaifuArt, ...]:
    return tuple(declared_art(character_id) for character_id in sorted(CHARACTERS))




def variant_art_candidates_for(character_id: str, variant: str) -> tuple[str, ...]:
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    safe_variant = variant.casefold()
    if safe_variant not in {"normal", "shiny"}:
        raise ValueError("variant must be normal or shiny")
    root = PurePosixPath("assets", "waifus")
    return tuple(
        str(root / f"{character_id}--{safe_variant}{suffix}")
        for suffix in RUNTIME_ART_SUFFIXES
    )
