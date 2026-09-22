import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "engine" / "waifumon" / "src" / "main" / "resources" / "waifumon"


def _load(name: str):
    return json.loads((RESOURCE_DIR / name).read_text(encoding="utf-8"))


def test_card_schema_exposes_normalized_waifumon_fields() -> None:
    schema = _load("card-schema.json")
    assert schema["required"] == [
        "card_id",
        "name",
        "base_atk",
        "base_def",
        "element_type",
        "skills",
    ]
    assert "base_hp" in schema["properties"]
    assert "cost" in schema["properties"]
    skill_effect = schema["properties"]["skills"]["items"]["properties"]["skill_effect"]
    assert set(skill_effect["properties"]["effect_type"]["enum"]) >= {
        "damage",
        "heal",
        "shield",
        "apply_status",
    }


def test_sample_cards_follow_the_normalized_contract() -> None:
    cards = _load("cards.sample.json")
    assert cards
    for card in cards:
        assert card["card_id"]
        assert card["base_atk"] > 0
        assert card["base_def"] > 0
        assert card["element_type"]
        assert card["skills"]
        for skill in card["skills"]:
            assert skill["skill_id"]
            assert skill["skill_effect"]["effect_type"]


def test_combat_resource_matches_current_engine_contract() -> None:
    formula = _load("combat-formula.json")
    assert formula["formula_id"] == "waifumon-v1"
    assert formula["elements"]["strong"] == 1.25
    assert formula["elements"]["neutral"] == 1.0
    assert formula["elements"]["resist"] == 0.75
    assert formula["elements"]["override_allowed"] is False
    assert formula["elements"]["strong_against"] == {
        "fuego": "hielo",
        "hielo": "aire",
        "aire": "tierra",
        "tierra": "rayo",
        "rayo": "agua",
        "agua": "fuego",
        "luz": "oscuridad",
        "oscuridad": "mente",
        "mente": "arcano",
        "arcano": "luz",
    }
    assert formula["critical"]["default_multiplier"] == 1.5
    assert "Math.random" in formula["randomness"]["forbidden"]


def test_status_and_turn_resources_are_explicit_data() -> None:
    statuses = _load("status-effects.json")["effects"]
    phases = _load("turn-phases.json")["phases"]

    assert {item["status_id"] for item in statuses} >= {
        "poison",
        "bleed",
        "stun",
        "shield",
    }
    assert [phase["id"] for phase in phases] == [
        "DRAW",
        "ACTION",
        "RESOLUTION",
        "CLEANUP",
        "END",
    ]
