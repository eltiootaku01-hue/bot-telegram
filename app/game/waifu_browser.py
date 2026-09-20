from __future__ import annotations

from dataclasses import dataclass

from app.game.catalog import CHARACTERS
from app.game.models import Character


PAGE_SIZE = 8


@dataclass(frozen=True, slots=True)
class WaifuPage:
    page: int
    total_pages: int
    characters: tuple[Character, ...]


def page_for(page: int) -> WaifuPage:
    """Return a deterministic page of the current playable waifu catalog."""
    characters = tuple(
        sorted(
            CHARACTERS.values(),
            key=lambda character: (
                character.popularity_rank is None,
                character.popularity_rank or 10_000,
                character.name.casefold(),
            ),
        )
    )
    total_pages = max(1, (len(characters) + PAGE_SIZE - 1) // PAGE_SIZE)
    safe_page = min(max(page, 1), total_pages)
    start = (safe_page - 1) * PAGE_SIZE
    return WaifuPage(
        page=safe_page,
        total_pages=total_pages,
        characters=characters[start : start + PAGE_SIZE],
    )


def render_page(page: WaifuPage) -> str:
    lines = [
        f"📚 <b>Catálogo de waifus</b> · página {page.page}/{page.total_pages}",
        "",
    ]
    for character in page.characters:
        ranking = f"#{character.popularity_rank}" if character.popularity_rank is not None else "sin ranking"
        lines.append(
            f"• <b>{character.name}</b> — {character.card_tier.value} · "
            f"clase {character.rarity.value} · {character.element.value}"
        )
        lines.append(
            f"  ⚡ Poder {character.power_score}/100 · ⭐ Popularidad {character.popularity_score}/100 · "
            f"ranking {ranking}"
        )
    return "\\n".join(lines)
