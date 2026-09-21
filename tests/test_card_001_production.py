import json
from pathlib import Path

from app.game.card_art_assets import validate_card_asset


def test_card_001_manifest_state_matches_generated_assets() -> None:
    qa = json.loads(Path("assets/waifus/card_art_qa_manifest.json").read_text(encoding="utf-8"))
    item = next(x for x in qa["items"] if x["character_id"] == "alisa-kujo")

    assert item["approved"] is True
    assert item["production_file"] == "assets/production/cards/alisa-kujo--normal.jpg"
    assert item["stage_assets"][0]["status"] == "approved_auxiliary"
    assert item["stage_assets"][1]["status"] == "approved_canonical"
    assert item["stage_assets"][2]["status"] == "primary_review_passed_second_review_required"


def test_card_001_assets_are_valid_1024x1536_jpegs() -> None:
    paths = [
        Path("assets/production/cards/alisa-kujo--r.jpg"),
        Path("assets/production/cards/alisa-kujo--normal.jpg"),
        Path("assets/quarantine/card_stages/alisa-kujo--ur.jpg"),
    ]
    for path in paths:
        result = validate_card_asset(path)
        assert result.valid
        assert (result.width, result.height) == (1024, 1536)
