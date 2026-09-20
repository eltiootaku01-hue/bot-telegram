from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.anime_catalog import AnimeCatalogService


@dataclass(frozen=True, slots=True)
class AnimeImportReport:
    works_seen: int
    characters_seen: int
    works_written: int
    characters_written: int


def _text(data: Mapping[str, object], key: str, *, required: bool = False) -> str:
    value = data.get(key)
    if value is None:
        if required:
            raise ValueError(f"missing required field: {key}")
        return ""
    if not isinstance(value, str):
        raise ValueError(f"field {key!r} must be a string")
    return value.strip()


def _string_tuple(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"field {key!r} must be a list of strings")
    return tuple(item.strip() for item in value if item.strip())


def _string_dict(data: Mapping[str, object], key: str) -> dict[str, str]:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(
        isinstance(name, str) and isinstance(item, str)
        for name, item in value.items()
    ):
        raise ValueError(f"field {key!r} must be an object of string values")
    return {
        name.strip(): item.strip()
        for name, item in value.items()
        if name.strip() and item.strip()
    }


def _optional_int(data: Mapping[str, object], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"field {key!r} must be an integer or null")
    return value


def _optional_date(data: Mapping[str, object], key: str) -> datetime | None:
    value = _text(data, key)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"field {key!r} must be an ISO datetime") from exc


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def load_import_file(path: str | Path) -> dict[str, object]:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read import file: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in import file {source}: line {exc.lineno}") from exc

    payload = _object(document, "catalog")
    works = payload.get("works")
    if not isinstance(works, list):
        raise ValueError("top-level field 'works' must be a list")
    return dict(payload)


async def import_payload(
    session: AsyncSession,
    payload: Mapping[str, object],
    *,
    service: AnimeCatalogService | None = None,
) -> AnimeImportReport:
    catalog = service or AnimeCatalogService()
    works_value = payload.get("works")
    if not isinstance(works_value, list):
        raise ValueError("top-level field 'works' must be a list")

    works_written = 0
    characters_written = 0

    for index, raw_work in enumerate(works_value):
        work = _object(raw_work, f"works[{index}]")
        work_id = _text(work, "id", required=True)
        title = _text(work, "title", required=True)
        characters = work.get("characters", [])
        if not isinstance(characters, list):
            raise ValueError(f"works[{index}].characters must be a list")

        await catalog.upsert_work(
            session,
            work_id=work_id,
            title=title,
            titles=_string_tuple(work, "titles"),
            media_type=_text(work, "type") or "unknown",
            status=_text(work, "status") or "unverified",
            year_start=_optional_int(work, "year_start"),
            year_end=_optional_int(work, "year_end"),
            episodes=_optional_int(work, "episodes"),
            genres=_string_tuple(work, "genres"),
            themes=_string_tuple(work, "themes"),
            studio=_text(work, "studio") or None,
            source_ids=_string_dict(work, "source_ids"),
            source_urls=_string_tuple(work, "source_urls"),
            summary_short=_text(work, "summary_short"),
            notes=_string_tuple(work, "notes"),
            last_verified=_optional_date(work, "last_verified"),
        )
        works_written += 1

        for character_index, raw_character in enumerate(characters):
            character = _object(
                raw_character,
                f"works[{index}].characters[{character_index}]",
            )
            await catalog.add_character(
                session,
                character_id=_text(character, "id", required=True),
                work_id=work_id,
                name=_text(character, "name", required=True),
                aliases=_string_tuple(character, "aliases"),
                source_ids=_string_dict(character, "source_ids"),
                source_urls=_string_tuple(character, "source_urls"),
                notes=_text(character, "notes"),
                last_verified=_optional_date(character, "last_verified"),
            )
            characters_written += 1

    return AnimeImportReport(
        works_seen=len(works_value),
        characters_seen=characters_written,
        works_written=works_written,
        characters_written=characters_written,
    )


async def import_file(
    session: AsyncSession,
    path: str | Path,
    *,
    service: AnimeCatalogService | None = None,
) -> AnimeImportReport:
    payload = load_import_file(path)
    return await import_payload(session, payload, service=service)
