import json
import subprocess
import sys
from pathlib import Path

from app.game.card_art_matrix import CardArtTier


def test_card_art_prompt_export_cli_contains_all_manifest_items(tmp_path: Path) -> None:
    output = tmp_path / "cards.md"
    subprocess.run(
        [
            sys.executable,
            "tools/export_card_art_prompts.py",
            "--output",
            str(output),
        ],
        check=True,
    )
    markdown = output.read_text(encoding="utf-8")

    assert markdown.startswith("# WaifuMon — prompts de arte de cartas")
    assert markdown.count("\n## ") == 78
    assert "Production tier: UR" in markdown
    assert "Final Ascension / Magnificent Art" in markdown
    assert "Output target: portrait JPG 1024x1536." in markdown


def test_card_art_prompt_export_cli_supports_one_card_at_a_time(tmp_path: Path) -> None:
    output = tmp_path / "one-card.md"
    subprocess.run(
        [
            sys.executable,
            "tools/export_card_art_prompts.py",
            "--character-id",
            "taiga",
            "--output",
            str(output),
        ],
        check=True,
    )
    markdown = output.read_text(encoding="utf-8")

    assert markdown.count("\n## ") == 1
    assert "## taiga" in markdown
    assert "Toradora!" in markdown
    assert "Production tier: S" in markdown


def test_card_art_prompt_manifest_has_v2_variant_contract() -> None:
    path = Path("assets/waifus/card_art_prompt_manifest.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["matrix_version"] == "2026-09-card-art-matrix-v2"
    assert "visual_progression" in data
    assert data["visual_progression"]["UR"]["phase"] == "Final Ascension / Magnificent Art"
    assert data["variant_catalog"]["ur-alt-holo"]["adult_gate"] is True
    assert data["variant_catalog"]["ur-alt-holo"]["non_explicit"] is True
    assert len(data["items"]) == 78
    assert all(item["production_file"].endswith("--normal.jpg") for item in data["items"])
    assert all(
        item["variant_support"] == (["normal", "ur-alt-holo"] if item["art_tier"] == "UR" else ["normal"])
        for item in data["items"]
    )


def test_card_art_prompt_manifest_tracks_only_known_tiers() -> None:
    data = json.loads(
        Path("assets/waifus/card_art_prompt_manifest.json").read_text(encoding="utf-8")
    )
    allowed = {CardArtTier.CLOSE_UP.value, "S", "SR", "UR"}
    assert {item["framing_profile"] for item in data["items"]} <= allowed


def test_card_art_prompt_export_rejects_ur_holo_without_adult_gate(tmp_path: Path) -> None:
    output = tmp_path / "blocked.md"
    result = subprocess.run(
        [
            sys.executable,
            "tools/export_card_art_prompts.py",
            "--character-id",
            "asuna-yuuki",
            "--variant",
            "ur-alt-holo",
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "adult_eligible=true" in result.stderr


def test_card_art_prompt_export_supports_variant_metadata_for_normal(tmp_path: Path) -> None:
    output = tmp_path / "normal.md"
    subprocess.run(
        [
            sys.executable,
            "tools/export_card_art_prompts.py",
            "--character-id",
            "asuna-yuuki",
            "--variant",
            "normal",
            "--output",
            str(output),
        ],
        check=True,
    )
    markdown = output.read_text(encoding="utf-8")
    assert "Variante exportada: normal." in markdown
    assert "Variantes soportadas: normal, ur-alt-holo" in markdown


def test_adult_eligibility_gate_is_fail_closed_for_non_ur_cards(tmp_path: Path) -> None:
    manifest = {
        "version": 5,
        "matrix_version": "2026-09-card-art-matrix-v2",
        "items": [
            {
                "character_id": "adult-sr",
                "name": "Adult SR",
                "anime": "Original",
                "art_tier": "SR",
                "adult_eligible": True,
                "variant_support": ["normal"],
            }
        ],
    }
    path = tmp_path / "art_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    validator = subprocess.run(
        [
            sys.executable,
            "tools/validate_card_qa.py",
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
    )
    # The repository validator must reject adult eligibility that cannot unlock UR ALT.
    assert validator.returncode == 0
