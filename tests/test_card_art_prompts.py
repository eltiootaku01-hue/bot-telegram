import json
import subprocess
import sys
from pathlib import Path

from app.game.card_art_matrix import CardArtTier


def test_card_art_prompt_export_uses_all_manifest_items() -> None:
    manifest = json.loads(Path("assets/waifus/art_manifest.json").read_text(encoding="utf-8"))
    from app.game.card_art_matrix import build_card_art_prompt, art_profile

    lines = []
    for item in manifest["items"]:
        profile = art_profile(item["art_tier"])
        lines.append(
            f"## {item['character_id']}\n"
            f"{build_card_art_prompt(character_name=item['name'], anime=item['anime'], tier=item['art_tier'])}"
            f"\nTier: {profile.tier.value}"
        )
    markdown = "\n".join(lines)

    assert len(manifest["items"]) == 78
    assert markdown.startswith("# WaifuMon — prompts de arte de cartas")
    assert markdown.count("\n## ") == 78
    assert "Production tier: UR" in markdown
    assert "Output JPG 1024x1536." in markdown


def test_card_art_prompt_export_cli_writes_non_empty_file(tmp_path: Path) -> None:
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
    assert output.is_file()
    assert output.stat().st_size > 0


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
