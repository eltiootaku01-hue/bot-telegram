from app.characters.repertoire import REPERTOIRE
from app.core.identity import BotIdentity
from app.services.world_catalog import WORLD_CATALOG, catalog_for_identity


def test_world_catalog_has_all_bot_workplaces_and_relationships() -> None:
    for identity in BotIdentity:
        entries = catalog_for_identity(identity)
        assert entries
        assert any(item.entry_type == "place" for item in entries)
        assert any(item.entry_type in {"role", "action"} for item in entries)

    relationships = [item for item in WORLD_CATALOG if item.entry_type == "relationship"]
    assert {
        item.entry_key for item in relationships
    } >= {"cari-cami", "cari-sunna", "cami-sunna", "chie-sunna"}


def test_world_catalog_keys_are_unique_per_identity_and_type() -> None:
    keys = [
        (item.bot_identity, item.entry_type, item.entry_key)
        for item in WORLD_CATALOG
    ]
    assert len(keys) == len(set(keys))


def test_world_catalog_has_cafe_and_waifumon_core_entries() -> None:
    assert any(
        item.entry_key == "cafe_otaku" and item.bot_identity is BotIdentity.CARI
        for item in WORLD_CATALOG
    )
    assert any(
        item.entry_key == "waifumon" and item.bot_identity is BotIdentity.SUNNA
        for item in WORLD_CATALOG
    )


import pytest
from sqlalchemy import select

from app.db.database import Database
from app.db.world_models import WorldCatalogEntry


@pytest.mark.asyncio
async def test_world_catalog_seed_is_idempotent() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()

    from app.services.world import WorldService

    service = WorldService()
    async with database.session() as session:
        await service.seed_catalog(session)
    async with database.session() as session:
        await service.seed_catalog(session)

    async with database.session() as session:
        rows = list(await session.scalars(select(WorldCatalogEntry)))

    assert len(rows) == len(WORLD_CATALOG) + len(REPERTOIRE)
    keys = [(row.bot_identity, row.entry_type, row.entry_key) for row in rows]
    assert len(keys) == len(set(keys))
    await database.close()
