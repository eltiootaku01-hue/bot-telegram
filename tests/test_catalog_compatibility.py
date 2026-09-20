from app.game.catalog import canonical_character_id, get_character


def test_legacy_character_ids_resolve_without_migration() -> None:
    assert canonical_character_id("anya-forger") == "anya"
    assert get_character("anya-forger").id == "anya"
