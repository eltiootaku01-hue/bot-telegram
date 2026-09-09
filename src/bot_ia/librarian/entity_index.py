"""Índice local y conservador de entidades identificables."""

from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath

from bot_ia.core.models import EntityCandidate

from .models import CatalogEntry


class EntityIndex:
    """Construye y consulta candidatos de entidades a partir de fuentes catalogadas."""

    def __init__(self, entries: tuple[CatalogEntry, ...]) -> None:
        self._entries = entries
        self._candidates, self._entries_by_entity = self._build_indexes(entries)

    @property
    def candidates(self) -> tuple[EntityCandidate, ...]:
        return self._candidates

    def for_universe(self, universe_id: str) -> tuple[EntityCandidate, ...]:
        return tuple(
            candidate
            for candidate in self._candidates
            if candidate.universe_id == universe_id
        )

    def entries_for(self, entity_id: str) -> tuple[CatalogEntry, ...]:
        return self._entries_by_entity.get(entity_id, ())

    @staticmethod
    def _build_indexes(
        entries: tuple[CatalogEntry, ...],
    ) -> tuple[
        tuple[EntityCandidate, ...],
        dict[str, tuple[CatalogEntry, ...]],
    ]:
        candidates: list[EntityCandidate] = []
        entries_by_entity: dict[str, list[CatalogEntry]] = {}
        seen_ids: set[str] = set()

        for entry in entries:
            frontmatter = _parse_frontmatter(entry.content)

            if not _looks_like_character(entry, frontmatter):
                continue

            entity_id = _scalar(frontmatter.get("id"))
            name = _scalar(frontmatter.get("name"))

            if not entity_id or not name:
                continue

            if entity_id not in seen_ids:
                candidates.append(
                    EntityCandidate(
                        entity_id=entity_id,
                        universe_id=entry.record.universe_id,
                        name=name,
                        aliases=_aliases(frontmatter.get("aliases")),
                    )
                )
                seen_ids.add(entity_id)

            entries_by_entity.setdefault(entity_id, []).append(entry)

        frozen_entries = {
            entity_id: tuple(
                sorted(
                    entity_entries,
                    key=lambda item: str(item.record.path).replace("\\", "/"),
                )
            )
            for entity_id, entity_entries in entries_by_entity.items()
        }

        frozen_candidates = tuple(
            sorted(
                candidates,
                key=lambda item: (
                    item.universe_id,
                    item.entity_id,
                ),
            )
        )

        return frozen_candidates, frozen_entries


def _looks_like_character(
    entry: CatalogEntry,
    frontmatter: dict[str, object],
) -> bool:
    """Acepta solo fichas claramente identificables como personajes."""
    declared_type = _scalar(frontmatter.get("type"))

    if declared_type == "character":
        return True

    path = PurePosixPath(str(entry.record.path))
    return "characters" in path.parts


def _parse_frontmatter(content: str) -> dict[str, object]:
    lines = content.splitlines()

    if not lines or lines[0].strip() != "---":
        return {}

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break

    if end is None:
        return {}

    values: dict[str, object] = {}
    current_list_key: str | None = None
    current_list: list[object] = []

    def flush_list() -> None:
        nonlocal current_list_key, current_list

        if current_list_key is not None:
            values[current_list_key] = list(current_list)

        current_list_key = None
        current_list = []

    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        list_match = re.match(
            r"^\s*-\s*(.*?)\s*$",
            line,
        )

        if list_match and current_list_key is not None:
            current_list.append(
                _parse_value(list_match.group(1))
            )
            continue

        match = re.match(
            r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$",
            line,
        )

        if not match:
            continue

        flush_list()

        key, raw_value = match.groups()

        if raw_value == "":
            current_list_key = key
            current_list = []
        else:
            values[key] = _parse_value(raw_value)

    flush_list()

    return values


def _parse_value(raw: str) -> object:
    if not raw:
        return ""

    if raw.startswith(("'", '"')) and raw.endswith(raw[0]):
        try:
            return ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return raw[1:-1]

    if raw.startswith("[") and raw.endswith("]"):
        try:
            value = ast.literal_eval(raw)
            if isinstance(value, list):
                return value
        except (SyntaxError, ValueError):
            pass

    return raw


def _scalar(value: object) -> str:
    if isinstance(value, str):
        return value.strip()

    return ""


def _aliases(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()

    aliases: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            continue

        alias = item.strip()

        if alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)

    return tuple(aliases)