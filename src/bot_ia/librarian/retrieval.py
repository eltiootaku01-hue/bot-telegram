"""Búsqueda léxica pequeña, filtrada y determinista."""

from __future__ import annotations

import re
import unicodedata

from .models import CatalogEntry, Fragment, RetrievalQuery


_STOPWORDS = frozenset(
    {
        "a",
        "al",
        "con",
        "como",
        "de",
        "del",
        "el",
        "en",
        "es",
        "la",
        "las",
        "lo",
        "los",
        "para",
        "por",
        "se",
        "su",
        "un",
        "una",
        "y",
        "que",
        "quien",
        "cuando",
        "donde",
    }
)


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())

    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def query_terms(text: str) -> tuple[str, ...]:
    normalized = _normalize_text(text)

    return tuple(
        dict.fromkeys(
            term
            for term in re.findall(
                r"[\w]+",
                normalized,
                flags=re.UNICODE,
            )
            if len(term) > 1 and term not in _STOPWORDS
        )
    )


def is_allowed(
    entry: CatalogEntry,
    query: RetrievalQuery,
) -> bool:
    temporal = entry.metadata.temporal
    spoiler = entry.metadata.spoiler

    if spoiler.level > query.max_spoiler:
        return False

    if (
        query.allowed_mediums
        and temporal.medium not in query.allowed_mediums
    ):
        return False

    if (
        query.allowed_arcs
        and temporal.arc not in query.allowed_arcs
    ):
        return False

    if (
        query.up_to_chapter is not None
        and temporal.chapter_start is not None
        and temporal.chapter_start > query.up_to_chapter
    ):
        return False

    return True


def _heading_score(
    block_lines: list[str],
    terms: set[str],
) -> float:
    """Mide la coincidencia entre la consulta y el encabezado de entidad."""
    if not block_lines or not terms:
        return 0.0

    first_line = block_lines[0].strip()

    if not first_line.startswith("### "):
        return 0.0

    heading = first_line[4:].strip()
    heading_terms = set(query_terms(heading))

    if not heading_terms:
        return 0.0

    overlap = len(terms & heading_terms)

    return overlap / len(terms)


def _fragment_score(
    text: str,
    block_lines: list[str],
    terms: set[str],
) -> float:
    """
    Puntúa un fragmento.

    Una entidad cuyo encabezado coincide directamente con la consulta
    obtiene 1.0.

    Una mera mención de la entidad en el cuerpo queda por debajo,
    para evitar que una referencia incidental empate con la ficha.
    """
    if not terms:
        return 0.0

    words = set(query_terms(text))
    overlap = len(terms & words)

    if not overlap:
        return 0.0

    base_score = overlap / len(terms)
    heading_score = _heading_score(
        block_lines,
        terms,
    )

    if heading_score >= 1.0:
        return 1.0

    if heading_score > 0.0:
        return round(
            min(
                0.95,
                base_score + (0.10 * heading_score),
            ),
            4,
        )

    return round(
        min(
            0.70,
            base_score * 0.70,
        ),
        4,
    )


def extract_fragments(
    entry: CatalogEntry,
    query: RetrievalQuery,
) -> tuple[Fragment, ...]:
    terms = set(query_terms(query.text))

    if not terms:
        return ()

    fragments: list[Fragment] = []
    lines = entry.content.splitlines()

    content_start = 0

    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                content_start = index + 1
                break

    blocks: list[tuple[int, list[str], str]] = []

    block: list[str] = []
    start = content_start + 1
    section = ""
    block_section = ""

    for number in range(
        content_start,
        len(lines),
    ):
        line = lines[number]
        stripped = line.strip()

        # Las secciones ## actualizan el contexto.
        if stripped.startswith("## "):
            if block:
                blocks.append(
                    (
                        start,
                        block,
                        block_section,
                    )
                )
                block = []

            section = stripped[3:].strip()
            continue

        # Los encabezados # son estructura documental.
        if stripped.startswith("# "):
            if block:
                blocks.append(
                    (
                        start,
                        block,
                        block_section,
                    )
                )
                block = []

            continue

        # Cada ### inicia una entidad independiente.
        if stripped.startswith("### "):
            if block:
                blocks.append(
                    (
                        start,
                        block,
                        block_section,
                    )
                )
                block = []

            start = number + 1
            block_section = section
            block.append(line)
            continue

        if stripped:
            if not block:
                start = number + 1
                block_section = section

            block.append(line)

        elif block:
            blocks.append(
                (
                    start,
                    block,
                    block_section,
                )
            )
            block = []

    if block:
        blocks.append(
            (
                start,
                block,
                block_section,
            )
        )

    for ordinal, (
        line_start,
        block_lines,
        block_section,
    ) in enumerate(
        blocks,
        start=1,
    ):
        text = "\n".join(block_lines)

        lexical_score = _fragment_score(
            text,
            block_lines,
            terms,
        )

        if lexical_score <= 0.0:
            continue

        fragments.append(
            Fragment(
                entry.record.source_id,
                entry.record.universe_id,
                ordinal,
                line_start,
                line_start + len(block_lines) - 1,
                text,
                lexical_score,
                block_section,
            )
        )

    return tuple(
        sorted(
            fragments,
            key=lambda item: (
                -item.lexical_score,
                item.ordinal,
            ),
        )
    )