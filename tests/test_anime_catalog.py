from datetime import datetime

import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.models import AnimeCharacter, AnimeWork
from app.services.anime_catalog import AnimeCatalogService


@pytest.mark.asyncio
async def test_anime_catalog_upserts_work_and_character(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'anime.db'}")
    await database.create_schema()
    service = AnimeCatalogService()
    verified = datetime(2026, 9, 19, 12, 0, 0)

    async with database.session() as session:
        work = await service.upsert_work(
            session,
            work_id="anime.test.1",
            title="Obra de prueba",
            titles=("Alias Uno", "Alias Uno"),
            media_type="tv",
            status="verified",
            genres=("action", "action"),
            themes=("adventure",),
            source_ids={"wikidata": "Q1"},
            source_urls=("https://example.invalid/source",),
            summary_short="Resumen original de prueba.",
            notes=("Verificado manualmente.",),
            last_verified=verified,
        )
        character = await service.add_character(
            session,
            character_id="anime.test.1:hero",
            work_id="anime.test.1",
            name="Heroína",
            aliases=("Hero",),
            source_ids={"wikidata": "Q2"},
            source_urls=("https://example.invalid/character",),
            last_verified=verified,
        )

    assert work.titles == ("Alias Uno",)
    assert work.genres == ("action",)
    assert work.source_ids == {"wikidata": "Q1"}
    assert character.work_id == "anime.test.1"

    async with database.session() as session:
        fetched = await service.get_work(session, "anime.test.1")
        found = await service.search_works(session, "Alias Uno")
        characters = await service.characters_for_work(session, "anime.test.1")

    assert fetched is not None
    assert fetched.title == "Obra de prueba"
    assert found and found[0].id == "anime.test.1"
    assert characters and characters[0].name == "Heroína"
    await database.close()


def test_anime_catalog_rejects_inverted_year_range() -> None:
    service = AnimeCatalogService()
    import asyncio

    async def run() -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        await database.create_schema()
        async with database.session() as session:
            with pytest.raises(ValueError, match="year_end"):
                await service.upsert_work(
                    session,
                    work_id="invalid-years",
                    title="Invalid",
                    year_start=2024,
                    year_end=2023,
                )
        await database.close()

    asyncio.run(run())


@pytest.mark.asyncio
async def test_anime_catalog_rejects_missing_work_for_character(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'anime-invalid.db'}")
    await database.create_schema()
    service = AnimeCatalogService()

    async with database.session() as session:
        with pytest.raises(ValueError, match="does not exist"):
            await service.add_character(
                session,
                character_id="missing:hero",
                work_id="missing-work",
                name="Hero",
            )

    await database.close()


@pytest.mark.asyncio
async def test_anime_catalog_search_is_local_and_limited(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'anime-search.db'}")
    await database.create_schema()
    service = AnimeCatalogService()

    async with database.session() as session:
        for index in range(12):
            await service.upsert_work(
                session,
                work_id=f"anime.{index}",
                title=f"Obra {index}",
                status="unverified",
            )

    async with database.session() as session:
        rows = await service.search_works(session, "", limit=10)
        persisted = list(await session.scalars(select(AnimeWork)))

    assert len(rows) == 10
    assert len(persisted) == 12
    await database.close()


@pytest.mark.asyncio
async def test_anime_catalog_data_uses_structured_provenance_fields(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'anime-source.db'}")
    await database.create_schema()
    service = AnimeCatalogService()

    async with database.session() as session:
        await service.upsert_work(
            session,
            work_id="anime.source",
            title="Fuente",
            source_ids={"mal": "123"},
            source_urls=("https://example.invalid/mal",),
        )

    async with database.session() as session:
        row = await session.get(AnimeWork, "anime.source")
        character_count = await session.scalar(
            select(AnimeCharacter.id).where(AnimeCharacter.work_id == "anime.source").limit(1)
        )

    assert row is not None
    assert "mal" in row.source_ids_json
    assert "example.invalid" in row.source_urls_json
    assert character_count is None
    await database.close()

@pytest.mark.asyncio
async def test_anime_catalog_search_finds_work_by_character_alias(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'anime-character-search.db'}")
    await database.create_schema()
    service = AnimeCatalogService()

    async with database.session() as session:
        await service.upsert_work(
            session,
            work_id="anime.character-search",
            title="Obra por personaje",
        )
        await service.add_character(
            session,
            character_id="anime.character-search:hero",
            work_id="anime.character-search",
            name="Asuna",
            aliases=("Yuuki", "heroína"),
        )

    async with database.session() as session:
        by_name = await service.search_works(session, "Asuna")
        by_alias = await service.search_works(session, "Yuuki")

    assert by_name and by_name[0].id == "anime.character-search"
    assert by_alias and by_alias[0].id == "anime.character-search"
    await database.close()
