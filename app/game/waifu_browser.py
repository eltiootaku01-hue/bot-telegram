from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.game.art_progression import art_frame_for
from app.game.catalog import CHARACTERS
from app.game.models import Character
from app.game.waifumon_progression import stats_for_character, class_band_for_level
from app.game.waifu_catalog import ANIME_CORNER_2025_SOURCE, RANKER_2026_SOURCE


PAGE_SIZE = 8


class WaifuFilterField(StrEnum):
    ELEMENT = "e"
    CARD = "c"
    RARITY = "r"
    SOURCE = "s"


@dataclass(frozen=True, slots=True)
class WaifuFilter:
    field: WaifuFilterField
    value: str

    @classmethod
    def from_code(cls, field: str, value: str) -> "WaifuFilter | None":
        try:
            parsed_field = WaifuFilterField(field)
        except ValueError:
            return None
        return cls(parsed_field, value)


@dataclass(frozen=True, slots=True)
class WaifuPage:
    page: int
    total_pages: int
    characters: tuple[Character, ...]
    active_filter: WaifuFilter | None = None


def _matches(character: Character, active_filter: WaifuFilter | None) -> bool:
    if active_filter is None:
        return True
    value = active_filter.value.casefold()
    if active_filter.field is WaifuFilterField.ELEMENT:
        return character.element.value.casefold() == value
    if active_filter.field is WaifuFilterField.CARD:
        return character.card_tier.value.casefold() == value
    if active_filter.field is WaifuFilterField.RARITY:
        return character.rarity.value.casefold() == value
    if active_filter.field is WaifuFilterField.SOURCE:
        if value == "ranker":
            return character.popularity_source == RANKER_2026_SOURCE
        if value == "recent":
            return character.popularity_source == ANIME_CORNER_2025_SOURCE
        if value == "local":
            return character.popularity_source == "Catálogo inicial del proyecto; pendiente de ranking externo."
        return False
    return False


def page_for(
    page: int,
    *,
    active_filter: WaifuFilter | None = None,
) -> WaifuPage:
    """Return a deterministic catalog page with an optional single filter."""
    characters = tuple(
        sorted(
            (character for character in CHARACTERS.values() if _matches(character, active_filter)),
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
        active_filter=active_filter,
    )


def filter_label(active_filter: WaifuFilter | None) -> str:
    if active_filter is None:
        return "Todos"
    labels = {
        (WaifuFilterField.ELEMENT, "fuego"): "Elemento: fuego",
        (WaifuFilterField.ELEMENT, "agua"): "Elemento: agua",
        (WaifuFilterField.ELEMENT, "tierra"): "Elemento: tierra",
        (WaifuFilterField.ELEMENT, "aire"): "Elemento: aire",
        (WaifuFilterField.ELEMENT, "hielo"): "Elemento: hielo",
        (WaifuFilterField.ELEMENT, "luz"): "Elemento: luz",
        (WaifuFilterField.ELEMENT, "oscuridad"): "Elemento: oscuridad",
        (WaifuFilterField.ELEMENT, "rayo"): "Elemento: rayo",
        (WaifuFilterField.ELEMENT, "mente"): "Elemento: mente",
        (WaifuFilterField.ELEMENT, "arcano"): "Elemento: arcano",
        (WaifuFilterField.ELEMENT, "neutro"): "Elemento: neutro",
        (WaifuFilterField.CARD, "r"): "Carta: R",
        (WaifuFilterField.CARD, "sr"): "Carta: SR",
        (WaifuFilterField.CARD, "ur"): "Carta: UR",
        (WaifuFilterField.RARITY, "d"): "Clase: D",
        (WaifuFilterField.RARITY, "c"): "Clase: C",
        (WaifuFilterField.RARITY, "b"): "Clase: B",
        (WaifuFilterField.RARITY, "a"): "Clase: A",
        (WaifuFilterField.RARITY, "s"): "Clase: S",
        (WaifuFilterField.RARITY, "ss"): "Clase: SS",
        (WaifuFilterField.RARITY, "sss"): "Clase: SSS",
        (WaifuFilterField.SOURCE, "ranker"): "Fuente: Ranker 2026",
        (WaifuFilterField.SOURCE, "recent"): "Fuente: Anime Corner 2025",
        (WaifuFilterField.SOURCE, "local"): "Fuente: catálogo inicial",
    }
    return labels.get((active_filter.field, active_filter.value.casefold()), "Filtro")


def render_page(page: WaifuPage) -> str:
    lines = [
        f"📚 <b>Catálogo de waifus</b> · página {page.page}/{page.total_pages}",
        f"🔎 <b>Filtro:</b> {filter_label(page.active_filter)}",
        "",
    ]
    for character in page.characters:
        ranking = (
            f"#{character.popularity_rank}"
            if character.popularity_rank is not None
            else "sin ranking"
        )
        lines.append(
            f"• <b>{character.name}</b> — {character.card_tier.value} · "
            f"clase {character.rarity.value} · {character.element.value}"
        )
        lines.append(
            f"  ⚡ Poder {character.power_score}/100 · "
            f"⭐ Popularidad {character.popularity_score}/100 · ranking {ranking}"
        )
    if not page.characters:
        lines.append("No hay personajes que coincidan con ese filtro.")
    return "\n".join(lines)


def source_label(character: Character) -> str:
    if character.popularity_source == RANKER_2026_SOURCE:
        return "Ranker · snapshot 2026-07-15"
    if character.popularity_source == ANIME_CORNER_2025_SOURCE:
        return "Anime Corner · ranking 2025"
    return "Catálogo inicial del proyecto"


def render_detail(character: Character, *, owned_level: int | None = None) -> str:
    level = owned_level or 1
    stats = stats_for_character(character, level)
    band = class_band_for_level(level)
    next_class = (
        class_band_for_level(band.max_level + 1).waifumon_class.value
        if band.max_level < 30
        else None
    )
    ranking = (
        f"#{character.popularity_rank}"
        if character.popularity_rank is not None
        else "sin ranking externo"
    )
    evolution_line = (
        f"🧬 WaifuMon: <b>{stats.waifumon_class.value}</b> · Nv.{stats.level}/30"
        + (f" · próxima clase: <b>{next_class}</b> al nivel {band.max_level + 1}" if next_class else " · clase máxima")
    )
    return "\n".join(
        (
            f"🎴 <b>{character.name}</b>",
            f"📺 {character.anime}",
            "",
            evolution_line,
            f"🎨 Arte: carta <b>{character.card_tier.value}</b> · {art_frame_for(card_tier=character.card_tier).visible_percent}",
            f"🧬 Arte evolutivo: <b>{stats.waifumon_class.value}</b> · {band.visible_percent} del personaje visible",
            f"🥊 Estilo de pelea: <b>{stats.style.value}</b>",
            "",
            f"❤️ Vida: <b>{stats.max_hp}</b>",
            f"💪 Fuerza: <b>{stats.strength}</b>",
            f"🛡️ Dureza: <b>{stats.defense}</b>",
            f"💨 Velocidad: <b>{stats.speed}</b>",
            f"💚 Curación: <b>{stats.healing}</b>",
            f"✨ Poder especial: <b>{stats.special_power}</b>",
            f"🔥 Habilidad de fuego: <b>{stats.fire_skill}</b>",
            f"🎯 Crítico: <b>{stats.critical_rate}%</b>",
            "",
            f"🏷️ Carta: <b>{character.card_tier.value}</b>",
            f"💠 Clase: <b>{character.rarity.value}</b> · rareza de combate",
            f"🌟 Elemento: <b>{character.element.value}</b>",
            f"⚡ Poder de balance: <b>{character.power_score}/100</b> · catálogo",
            f"⭐ Popularidad normalizada: <b>{character.popularity_score}/100</b>",
            f"📊 Ranking de referencia: <b>{ranking}</b>",
            f"📚 Procedencia: {source_label(character)}",
            "",
            "La clase WaifuMon evoluciona por nivel; la rareza D–SSS y el tier de carta son sistemas independientes.",
        )
    )
