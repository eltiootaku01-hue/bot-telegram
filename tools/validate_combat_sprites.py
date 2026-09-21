from __future__ import annotations

import json
import sys
from pathlib import Path

from app.game.combat_visuals import combat_sprite_path, validate_combat_sprite_asset


MANIFEST = Path("assets/waifus/combat_visual_manifest.json")


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    present = 0
    pending = 0

    items = data.get("items", [])
    if not isinstance(items, list):
        print("combat_visual_manifest.json: items must be a list", file=sys.stderr)
        return 1

    for item in items:
        character_id = str(item["character_id"])
        for variant in ("idle", "attack", "hit"):
            declared = item["battle_sprites"][variant]
            expected = combat_sprite_path(character_id, variant)
            if declared != expected:
                failures.append(
                    f"{character_id}/{variant}: manifest path {declared!r} != {expected!r}"
                )
                continue

            path = Path(expected)
            if not path.exists():
                pending += 1
                continue

            present += 1
            result = validate_combat_sprite_asset(path)
            print(
                f"{path}: valid={result.valid} "
                f"dimensions={result.width}x{result.height} "
                f"transparent={result.transparent} reason={result.reason}"
            )
            if not result.valid:
                failures.append(f"{path}: {result.reason}")

    expected_count = len(items) * 3
    if len(items) != 78:
        failures.append(f"manifest tracks {len(items)} cards; expected 78")
    if data.get("special_cut_in_ms") != 1500:
        failures.append("special_cut_in_ms must be exactly 1500")

    if failures:
        print("Combat sprite contract FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        f"Combat sprite contract validated: {len(items)} cards, "
        f"{expected_count} sprite slots declared, {present} assets present, {pending} pending."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
