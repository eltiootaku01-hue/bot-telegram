from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from app.game.card_art_assets import CARD_ART_EXTENSIONS, validate_card_asset

PRODUCTION_ROOT = Path("assets/production/cards")
QUARANTINE_ROOT = Path("assets/quarantine")


def _quarantine(path: Path) -> Path:
    QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)
    destination = QUARANTINE_ROOT / path.name
    if destination.exists():
        stem = destination.stem
        suffix = destination.suffix
        index = 2
        while destination.exists():
            destination = QUARANTINE_ROOT / f"{stem}--quarantine-{index}{suffix}"
            index += 1
    shutil.move(str(path), str(destination))
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate WaifuMon production card assets one by one."
    )
    parser.add_argument(
        "--quarantine-invalid",
        action="store_true",
        help="Move invalid production files into assets/quarantine/ after reporting them.",
    )
    args = parser.parse_args()

    if not PRODUCTION_ROOT.exists():
        print(
            f"No approved production card assets directory exists yet: {PRODUCTION_ROOT}. "
            "Structural validation passes; production remains empty and fail-closed."
        )
        return 0

    audited = 0
    failures: list[Path] = []
    unexpected_files: list[Path] = []

    for path in sorted(PRODUCTION_ROOT.rglob("*")):
        if not path.is_file():
            continue
        audited += 1
        if path.suffix.casefold() not in CARD_ART_EXTENSIONS:
            unexpected_files.append(path)
            print(f"{path}: invalid production extension", file=sys.stderr)
            continue

        result = validate_card_asset(path)
        print(
            f"{path}: valid={result.valid} "
            f"dimensions={result.width}x{result.height} "
            f"size={result.size_bytes} reason={result.reason}"
        )
        if not result.valid:
            failures.append(path)

    if args.quarantine_invalid:
        for path in [*unexpected_files, *failures]:
            if path.exists():
                destination = _quarantine(path)
                print(f"QUARANTINED: {path} -> {destination}")

    if unexpected_files or failures:
        print(
            "Invalid production card assets remain outside the production contract.",
            file=sys.stderr,
        )
        return 1

    if audited == 0:
        print(
            "Production asset directory is empty: structural contract is valid, "
            "but no card has passed visual/technical approval yet."
        )
    else:
        print(
            f"Production asset contract validated: {audited} asset(s), JPG/JPEG 1024x1536 only."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
