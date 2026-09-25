from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import AnimeCharacter, AnimeWork


@dataclass(frozen=True, slots=True)
class AnimeWorkRecord:
    id: str
    title: str
    titles: tuple[str, ...]
    media_type: str
    status: str
    year_start: int | None
    year_end: int | None
    episodes: int | None
    genres: tuple[str, ...]
    themes: tuple[str, ...]
    studio: str | None
    source_ids: dict[str, str]
    source_urls: tuple[str, ...]
    summary_short: str
    notes: tuple[str, ...]
    last_verified: datetime | None


@dataclass(frozen=True, slots=True)
class AnimeCharacterRecord:
    id: str
    work_id: str
    name: str
    aliases: tuple[str, ...]
    source_ids: dict[str, str]
    source_urls: tuple[str, ...]
    notes: str
    last_verified: datetime | None


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode_list(value: str) -> tuple[str, ...]:
    decoded = json.loads(value or "[]")
    if not isinstance(decoded, list):
        raise ValueError("expected JSON list")
    return tuple(str(item) for item in decoded)


def _decode_dict(value: str) -> dict[str, str]:
    decoded = json.loads(value or "{}")
    if not isinstance(decoded, dict):
        raise ValueError("expected JSON object")
    return {str(key): str(item) for key, item in decoded.items()}


def _work_record(row: AnimeWork) -> AnimeWorkRecord:
    return AnimeWorkRecord(
        id=row.id,
        title=row.title,
        titles=_decode_list(row.titles_json),
        media_type=row.media_type,
        status=row.status,
        year_start=row.year_start,
        year_end=row.year_end,
        episodes=row.episodes,
        genres=_decode_list(row.genres_json),
        themes=_decode_list(row.themes_json),
        studio=row.studio,
        source_ids=_decode_dict(row.source_ids_json),
        source_urls=_decode_list(row.source_urls_json),
        summary_short=row.summary_short,
        notes=_decode_list(row.notes_json),
        last_verified=row.last_verified,
    )


def _character_record(row: AnimeCharacter) -> AnimeCharacterRecord:
    return AnimeCharacterRecord(
        id=row.id,
        work_id=row.work_id,
        name=row.name,
        aliases=_decode_list(row.aliases_json),
        source_ids=_decode_dict(row.source_ids_json),
        source_urls=_decode_list(row.source_urls_json),
        notes=row.notes,
        last_verified=row.last_verified,
    )


class AnimeCatalogService:
    """Local-only anime/manga knowledge store.

    External import is an explicit operation. Runtime searches never call web
    providers, so network failures cannot change conversational behavior.
    """

    async def upsert_work(
        self,
        session: AsyncSession,
        *,
        work_id: str,
        title: str,
        titles: tuple[str, ...] = (),
        media_type: str = "unknown",
        status: str = "unverified",
        year_start: int | None = None,
        year_end: int | None = None,
        episodes: int | None = None,
        genres: tuple[str, ...] = (),
        themes: tuple[str, ...] = (),
        studio: str | None = None,
        source_ids: dict[str, str] | None = None,
        source_urls: tuple[str, ...] = (),
        summary_short: str = "",
        notes: tuple[str, ...] = (),
        last_verified: datetime | None = None,
    ) -> AnimeWorkRecord:
        if not work_id.strip():
            raise ValueError("work_id cannot be empty")
        if not title.strip():
            raise ValueError("title cannot be empty")
        if year_start is not None and not 1000 <= year_start <= 3000:
            raise ValueError("year_start is outside the supported range")
        if year_end is not None and not 1000 <= year_end <= 3000:
            raise ValueError("year_end is outside the supported range")
        if episodes is not None and episodes < 0:
            raise ValueError("episodes cannot be negative")
        if year_start is not None and year_end is not None and year_end < year_start:
            raise ValueError("year_end cannot be earlier than year_start")

        values = {
            "title": title.strip(),
            "titles_json": _json(tuple(dict.fromkeys(value.strip() for value in titles if value.strip()))),
            "media_type": media_type.strip() or "unknown",
            "status": status.strip() or "unverified",
            "year_start": year_start,
            "year_end": year_end,
            "episodes": episodes,
            "genres_json": _json(tuple(dict.fromkeys(value.strip() for value in genres if value.strip()))),
            "themes_json": _json(tuple(dict.fromkeys(value.strip() for value in themes if value.strip()))),
            "studio": studio.strip() if studio else None,
            "source_ids_json": _json(source_ids or {}),
            "source_urls_json": _json(tuple(dict.fromkeys(value.strip() for value in source_urls if value.strip()))),
            "summary_short": summary_short.strip(),
            "notes_json": _json(tuple(dict.fromkeys(value.strip() for value in notes if value.strip()))),
            "last_verified": last_verified,
            "updated_at": utc_now(),
        }

        existing = await session.get(AnimeWork, work_id)
        if existing is not None:
            await session.execute(
                update(AnimeWork).where(AnimeWork.id == work_id).values(**values)
            )
            await session.flush()
            refreshed = await session.get(AnimeWork, work_id)
            if refreshed is None:
                raise RuntimeError("Anime work disappeared after update")
            return _work_record(refreshed)

        row = AnimeWork(id=work_id.strip(), **values)
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            existing = await session.get(AnimeWork, work_id)
            if existing is None:
                raise
            await session.execute(
                update(AnimeWork).where(AnimeWork.id == work_id).values(**values)
            )
            await session.flush()
            refreshed = await session.get(AnimeWork, work_id)
            if refreshed is None:
                raise RuntimeError("Anime work disappeared after concurrent insert")
            return _work_record(refreshed)
        return _work_record(row)

    async def add_character(
        self,
        session: AsyncSession,
        *,
        character_id: str,
        work_id: str,
        name: str,
        aliases: tuple[str, ...] = (),
        source_ids: dict[str, str] | None = None,
        source_urls: tuple[str, ...] = (),
        notes: str = "",
        last_verified: datetime | None = None,
    ) -> AnimeCharacterRecord:
        if not character_id.strip():
            raise ValueError("character_id cannot be empty")
        if not name.strip():
            raise ValueError("character name cannot be empty")
        if await session.get(AnimeWork, work_id) is None:
            raise ValueError(f"Anime work does not exist: {work_id}")

        values = {
            "work_id": work_id,
            "name": name.strip(),
            "aliases_json": _json(tuple(dict.fromkeys(value.strip() for value in aliases if value.strip()))),
            "source_ids_json": _json(source_ids or {}),
            "source_urls_json": _json(tuple(dict.fromkeys(value.strip() for value in source_urls if value.strip()))),
            "notes": notes.strip(),
            "last_verified": last_verified,
            "updated_at": utc_now(),
        }

        existing = await session.get(AnimeCharacter, character_id)
        if existing is not None:
            await session.execute(
                update(AnimeCharacter).where(AnimeCharacter.id == character_id).values(**values)
            )
            await session.flush()
            refreshed = await session.get(AnimeCharacter, character_id)
            if refreshed is None:
                raise RuntimeError("Anime character disappeared after update")
            return _character_record(refreshed)

        row = AnimeCharacter(id=character_id.strip(), **values)
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            existing = await session.get(AnimeCharacter, character_id)
            if existing is None:
                raise
            await session.execute(
                update(AnimeCharacter).where(AnimeCharacter.id == character_id).values(**values)
            )
            await session.flush()
            refreshed = await session.get(AnimeCharacter, character_id)
            if refreshed is None:
                raise RuntimeError("Anime character disappeared after concurrent insert")
            return _character_record(refreshed)
        return _character_record(row)

    async def get_work(
        self,
        session: AsyncSession,
        work_id: str,
    ) -> AnimeWorkRecord | None:
        row = await session.get(AnimeWork, work_id)
        return _work_record(row) if row is not None else None

    async def search_works(
        self,
        session: AsyncSession,
        query: str,
        *,
        limit: int = 10,
    ) -> list[AnimeWorkRecord]:
        query = query.strip()
        if limit <= 0:
            return []
        if not query:
            rows = await session.scalars(
                select(AnimeWork).order_by(AnimeWork.title.asc()).limit(limit)
            )
        else:
            pattern = f"%{query}%"
            rows = await session.scalars(
                select(AnimeWork)
                .outerjoin(AnimeCharacter, AnimeCharacter.work_id == AnimeWork.id)
                .where(
                    or_(
                        AnimeWork.title.ilike(pattern),
                        AnimeWork.titles_json.ilike(pattern),
                        AnimeWork.genres_json.ilike(pattern),
                        AnimeWork.themes_json.ilike(pattern),
                        AnimeCharacter.name.ilike(pattern),
                        AnimeCharacter.aliases_json.ilike(pattern),
                    )
                )
                .distinct()
                .order_by(AnimeWork.title.asc())
                .limit(limit)
            )
        return [_work_record(row) for row in rows]

    async def characters_for_work(
        self,
        session: AsyncSession,
        work_id: str,
        *,
        limit: int = 20,
    ) -> list[AnimeCharacterRecord]:
        rows = await session.scalars(
            select(AnimeCharacter)
            .where(AnimeCharacter.work_id == work_id)
            .order_by(AnimeCharacter.name.asc())
            .limit(limit)
        )
        return [_character_record(row) for row in rows]
