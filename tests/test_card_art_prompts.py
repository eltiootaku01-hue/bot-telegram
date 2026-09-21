import json
from pathlib import Path

from tools.export_card_art_prompts import build_markdown, load_manifest


def test_card_art_prompt_export_uses_all_manifest_items() -> None:
    manifest = load_manifest(Path("assets/waifus/art_manifest.json"))
    markdown = build_markdown(manifest)

    assert len(manifest["items"]) == 78
    assert markdown.startswith("# WaifuMon — prompts de arte de cartas")
    assert markdown.count("
## ") == 78
    assert "Production tier: UR" in markdown
    assert "Output JPG 1024x1536." in markdown


def test_prompt_manifest_has_same_item_count() -> None:
    path = Path("assets/waifus/card_art_prompt_manifest.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["matrix_version"] == "2026-09-card-art-matrix-v1"
    assert len(data["items"]) == 78
    assert all(item["production_file"].endswith("--normal.jpg") for item in data["items"])
