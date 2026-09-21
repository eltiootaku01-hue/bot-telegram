from __future__ import annotations

import sys
from pathlib import Path

from app.game.card_art_assets import validate_card_asset


def main() -> int:
    root = Path("assets/waifus")
    assets = sorted(root.glob("*--normal.jpg")) + sorted(root.glob("*--shiny.jpg"))
    if not assets:
        print("No raster card assets are committed; registry validation remains available.")
        return 0

    failures = []
    for path in assets:
        result = validate_card_asset(path)
        print(
            f"{path}: valid={result.valid} "
            f"dimensions={result.width}x{result.height} "
            f"size={result.size_bytes} reason={result.reason}"
        )
        if not result.valid:
            failures.append(path)

    if failures:
        print("Invalid card assets:", file=sys.stderr)
        for path in failures:
            print(path, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
