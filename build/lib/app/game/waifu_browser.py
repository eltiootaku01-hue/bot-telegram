from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.game.art_progression import art_frame_for, waifumon_rarity_art_visibility
from app.game.catalog import CHARACTERS
from app.game.models import Character
from app.game.waifumon_progression import evolution_band_for_level, stats_for_character
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


def render_detail(
    character: Character,
    *,
    owned_level: int | None = None,
    potential_seed: str | None = None,
) -> str:
    """Render public discovery data or true owned stats after capture."""
    ranking = (
        f"#{character.popularity_rank}"
        if character.popularity_rank is not None
        else "sin ranking externo"
    )
    rarity_art = waifumon_rarity_art_visibility(character.rarity)
    card_frame = art_frame_for(card_tier=character.card_tier)
    lines = [
        f"🎴 <b>{character.name}</b>",
        f"📺 {character.anime}",
        "",
        f"💠 Clase WaifuMon: <b>{character.rarity.value}</b> · estadísticas de combate reales",
        f"🌟 Elemento: <b>{character.element.value}</b>",
        f"🎨 Arte: <b>{card_frame.tier.value}</b> · {card_frame.visible_percent}",
        f"🎨 Arte de clase: hasta <b>{rarity_art}</b> de visibilidad",
        f"🏷️ Carta: <b>{character.card_tier.value}</b> · datos mínimos",
    ]

    if owned_level is None:
        lines.extend(
            (
                "",
                "🔒 <b>Estadísticas reales:</b> ocultas.",
                "Capturala para revelar sus valores iniciales. Cada ejemplar obtiene un potencial individual persistente.",
                "📈 Nivel: 1/30 al obtenerla · el nivel sube con EXP y no cambia la clase.",
            )
        )
    else:
        stats = stats_for_character(
            character,
            owned_level,
            rarity=character.rarity,
            potential_seed=potential_seed,
        )
        band = evolution_band_for_level(owned_level)
        next_level = band.max_level + 1 if owned_level < 30 else None
        lines.extend(
            (
                "",
                f"🧬 Etapa de evolución: <b>{stats.evolution_stage.value}/3</b>"
                + (f" · próxima en Nv.{next_level}" if next_level else " · etapa final"),
                f"📈 Nivel: <b>{stats.level}/30</b> · EXP determina el nivel, no la clase",
                f"🎯 Potencial individual: <b>{stats.potential_score}/100</b>",
                "",
                f"❤️ Vida: <b>{stats.max_hp}</b>",
                f"💪 Fuerza: <b>{stats.strength}</b>",
                f"🛡️ Defensa: <b>{stats.defense}</b>",
                f"💨 Velocidad: <b>{stats.speed}</b>",
                f"✨ Especial: <b>{stats.special_power}</b>",
                f"🎯 Crítico: <b>{stats.critical_rate}%</b>",
                f"🎨 Arte evolutivo: <b>{band.stage.value}/3</b> · {band.art_visibility}",
            )
        )

    lines.extend(
        (
            "",
            f"⚡ Poder de catálogo: <b>{character.power_score}/100</b>",
            f"⭐ Popularidad normalizada: <b>{character.popularity_score}/100</b>",
            f"📊 Ranking de referencia: <b>{ranking}</b>",
            f"📚 Procedencia: {source_label(character)}",
            "",
            "La clase D–SSS es independiente del nivel 1–30. La carta no contiene las estadísticas reales del ejemplar.",
        )
    )
    return "\n".join(lines)
