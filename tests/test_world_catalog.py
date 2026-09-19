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
