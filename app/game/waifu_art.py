from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from app.game.catalog import CHARACTERS


@dataclass(frozen=True, slots=True)
class WaifuArt:
    character_id: str
    repository_path: str


def art_path_for(character_id: str) -> str:
    if character_id not in CHARACTERS:
        raise KeyError(character_id)
    return str(PurePosixPath("assets", "waifus", character_id + ".png"))


def declared_art(character_id: str) -> WaifuArt:
    return WaifuArt(character_id=character_id, repository_path=art_path_for(character_id))


def declared_art_for_catalog() -> tuple[WaifuArt, ...]:
    return tuple(declared_art(character_id) for character_id in sorted(CHARACTERS))

