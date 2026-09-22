import json
from pathlib import Path


CATALOG_PATH = Path(__file__).parents[1] / "webapp" / "data" / "cards_equipment.json"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_equipment_catalog_matches_expected_schema() -> None:
    catalog = load_catalog()

    assert catalog["catalog_version"] == "1.0.0"
    assert catalog["archetype"] == "Bōsōzoku Cyber-Tactical"
    cards = catalog["equipment_cards"]
    assert len(cards) == 4

    ids = {card["card_id"] for card in cards}
    assert ids == {
        "eq_shoulder_cannon_01",
        "eq_wings_booster_02",
        "eq_blade_katana_03",
        "eq_tactical_visor_04",
    }

    for card in cards:
        assert card["card_type"] == "EQUIPO"
        assert card["character_owner"] == "alisa_kujo"
        assert isinstance(card["cost"], int)
        assert card["cost"] >= 0
        assert isinstance(card["gameplay_effects"], dict)

        attachment = card["3d_attachment"]
        assert attachment["model_url"].startswith("assets/")
        assert attachment["target_bone"]
        assert attachment["socket_name"]

        for field in ("offset_position", "offset_rotation", "scale"):
            vector = attachment[field]
            assert len(vector) == 3
            assert all(isinstance(value, (int, float)) for value in vector)

        assert all(value > 0 for value in attachment["scale"])


def test_equipment_catalog_has_unique_assets_and_sockets() -> None:
    cards = load_catalog()["equipment_cards"]

    model_urls = [card["3d_attachment"]["model_url"] for card in cards]
    sockets = [card["3d_attachment"]["socket_name"] for card in cards]

    assert len(model_urls) == len(set(model_urls))
    assert len(sockets) == len(set(sockets))
