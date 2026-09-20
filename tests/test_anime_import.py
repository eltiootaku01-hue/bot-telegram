import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import AnimeCharacter, AnimeWork
from app.services.anime_import import import_file, load_import_file


def valid_document() -> dict:
    return {
        "works": [
            {
                "id": "imported.work",
                "title": "Imported Work",
                "titles": ["Alt"],
                "type": "tv",
                "status": "verified",
                "year_start": 2020,
                "year_end": 2021,
                "episodes": 24,
                "genres": ["action"],
                "themes": ["adventure"],
                "studio": "Studio",
                "source_ids": {"wikidata": "Q1"},
                "source_urls": ["https://example.invalid/work"],
                "summary_short": "Original short summary.",
                "notes": ["Checked"],
                "last_verified": "2026-09-19T12:00:00",
                "characters": [
                    {
                        "id": "imported.work:hero",
                        "name": "Hero",
                        "aliases": ["H"],
                        "source_ids": {"wikidata": "Q2"},
                        "source_urls": ["https://example.invalid/hero"],
                        "notes": "Local note",
                        "last_verified": "2026-09-19T12:00:00",
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_import_file_persists_work_and_character(tmp_path) -> None:
    source = tmp_path / "catalog.json"
    source.write_text(json.dumps(valid_document()), encoding="utf-8")

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'anime-import.db'}")
    await database.create_schema()

    async with database.session(write=True) as session:
        report = await import_file(session, source)

    assert report.works_seen == 1
    assert report.characters_seen == 1
    assert report.works_written == 1
    assert report.characters_written == 1

    async with database.session() as session:
        work = await session.get(AnimeWork, "imported.work")
        character = await session.get(AnimeCharacter, "imported.work:hero")

    assert work is not None
    assert work.status == "verified"
    assert work.last_verified == datetime(2026, 9, 19, 12, 0, 0)
    assert character is not None
    assert character.work_id == "imported.work"
    await database.close()


@pytest.mark.asyncio
async def test_import_file_rolls_back_on_invalid_character(tmp_path) -> None:
    document = valid_document()
    document["works"][0]["characters"][0]["name"] = ""
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(document), encoding="utf-8")

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'anime-import-rollback.db'}")
    await database.create_schema()

    with pytest.raises(ValueError, match="character name"):
        async with database.session(write=True) as session:
            await import_file(session, source)

    async with database.session() as session:
        works = list(await session.scalars(select(AnimeWork)))

    assert works == []
    await database.close()


def test_load_import_file_rejects_non_list_works(tmp_path) -> None:
    source = tmp_path / "bad.json"
    source.write_text(json.dumps({"works": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="works.*list"):
        load_import_file(source)


@pytest.mark.asyncio
async def test_import_file_rejects_timezone_aware_verification_timestamps(tmp_path) -> None:
    document = valid_document()
    document["works"][0]["last_verified"] = "2026-09-19T12:00:00-03:00"
    source = tmp_path / "aware.json"
    source.write_text(json.dumps(document), encoding="utf-8")

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'aware.db'}")
    await database.create_schema()

    with pytest.raises(ValueError, match="timezone-naive"):
        async with database.session(write=True) as session:
            await import_file(session, source)

    await database.close()
