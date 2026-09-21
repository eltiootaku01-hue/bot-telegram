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


def test_prompt_manifest_has_same_item_count() -> None:
    path = Path("assets/waifus/card_art_prompt_manifest.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["matrix_version"] == "2026-09-card-art-matrix-v1"
    assert len(data["items"]) == 78
    assert all(item["production_file"].endswith("--normal.jpg") for item in data["items"])


def test_card_art_prompt_manifest_tracks_only_known_tiers() -> None:
    data = json.loads(
        Path("assets/waifus/card_art_prompt_manifest.json").read_text(encoding="utf-8")
    )
    allowed = {CardArtTier.CLOSE_UP.value, "S", "SR", "UR"}
    assert {item["framing_profile"] for item in data["items"]} <= allowed
