import json
from pathlib import Path

from app.game.card_art_matrix import CardArtTier


def test_card_art_manifest_matches_definitive_matrix_contract() -> None:
    path = Path("assets/waifus/art_manifest.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["matrix_version"] == "2026-09-card-art-matrix-v1"
    assert data["production_contract"]["directory"] == "assets/production/cards/"
    assert set(data["production_contract"]["extensions"]) == {".jpg", ".jpeg"}
    assert (data["production_contract"]["width"], data["production_contract"]["height"]) == (1024, 1536)
    assert data["execution_rules"]["one_card_at_a_time"] is True
    assert data["execution_rules"]["visual_audit_required"] is True
    assert data["execution_rules"]["ur_double_review"] is True

    assert len(data["items"]) == 78
    valid_tiers = {tier.value for tier in CardArtTier if tier is not CardArtTier.CLOSE_UP} | {"S", "SR", "UR"}
    for item in data["items"]:
        assert item["framing_profile"] in {"D_C_B_R", *valid_tiers}
        assert item["visual_audit_status"] in {"not_inspected", "approved", "failed"}
        assert isinstance(item["adult_eligible"], bool)

    assert data["completed_items"] == 0
