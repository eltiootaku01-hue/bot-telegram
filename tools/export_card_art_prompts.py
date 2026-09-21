from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.game.card_art_matrix import art_profile, build_card_art_prompt


DEFAULT_MANIFEST = Path("assets/waifus/art_manifest.json")
DEFAULT_OUTPUT = Path("docs/generated/WAIFUMON_CARD_ART_PROMPTS.md")


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("Art manifest must be an object containing an items array")
    return data


def build_markdown(manifest: dict, character_id: str | None = None) -> str:
    items = manifest["items"]
    if character_id is not None:
        matches = [item for item in items if item.get("character_id") == character_id]
        if not matches:
            raise ValueError(f"Unknown character_id: {character_id}")
        items = matches

    lines = [
        "# WaifuMon — prompts de arte de cartas",
        "",
        "Generado desde `assets/waifus/art_manifest.json` y app/game/card_art_matrix.py.",
        "",
        "Producción individual: una carta por prompt, sin reutilizar el encuadre de otro tier.",
        "",
    ]
    for item in items:
        tier = str(item.get("art_tier", "")).strip()
        profile = art_profile(tier)
        prompt = build_card_art_prompt(
            character_name=str(item["name"]),
            anime=str(item.get("anime", "")),
            tier=tier,
            adult_eligible=bool(item.get("adult_eligible", False)),
            outfit_note=str(item.get("outfit_direction", "")),
            background_note=str(item.get("background_direction", "")),
        )
        lines.extend([
            f"## {item['character_id']}",
            f"- Personaje: {item['name']}",
            f"- Obra: {item.get('anime', '')}",
            f"- Art tier: {profile.tier.value}",
            f"- Encuadre: {profile.framing}",
            f"- Composición: {profile.composition}",
            f"- Vestuario: {profile.wardrobe}",
            f"- Elegibilidad adulta explícita en manifest: {bool(item.get('adult_eligible', False))}",
            f"- Estado del asset: {item.get('asset_status', 'pending')}",
            "",
            prompt,
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export WaifuMon card art prompts from the canonical manifest."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--character-id",
        help="Prepare exactly one card prompt instead of exporting the full catalog.",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_markdown(manifest), encoding="utf-8")
    print(f"Wrote {len(manifest['items'])} card prompts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
