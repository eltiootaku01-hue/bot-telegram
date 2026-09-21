from __future__ import annotations

import sys
from pathlib import Path

from app.game.card_art_assets import validate_card_asset

PRODUCTION_ROOT = Path("assets/production/cards")


def main() -> int:
    if not PRODUCTION_ROOT.exists():
        print(f"Missing production asset directory: {PRODUCTION_ROOT}", file=sys.stderr)
        return 1

    failures: list[Path] = []
    unexpected_files: list[Path] = []

    for path in sorted(PRODUCTION_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.casefold() != ".jpg":
            unexpected_files.append(path)
            continue

        result = validate_card_asset(path)
        print(
            f"{path}: valid={result.valid} "
            f"dimensions={result.width}x{result.height} "
            f"size={result.size_bytes} reason={result.reason}"
        )
        if not result.valid:
            failures.append(path)

    if unexpected_files:
        print("Non-JPEG files are not allowed in production:", file=sys.stderr)
        for path in unexpected_files:
            print(path, file=sys.stderr)

    if failures:
        print("Invalid production card assets:", file=sys.stderr)
        for path in failures:
            print(path, file=sys.stderr)

    if unexpected_files or failures:
        return 1

    print("Production asset contract validated: JPEG 1024x1536 only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
