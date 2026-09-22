from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from app.game.art_provenance import ALLOWED_PROVENANCE_STATUSES, validate_provenance
from app.game.card_art_assets import CARD_ART_EXTENSIONS, validate_card_asset

PRODUCTION_ROOT = Path("assets/production/cards")
QUARANTINE_ROOT = Path("assets/quarantine")
PROVENANCE_MANIFEST = Path("assets/waifus/provenance_manifest.json")

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate WaifuMon production card assets and their provenance."
    )
    parser.add_argument(
        "--quarantine-invalid",
        action="store_true",
        help="Move invalid production files into assets/quarantine/ after reporting them.",
    )
    args = parser.parse_args()

    provenance = _load_provenance()

    if not PRODUCTION_ROOT.exists():
        print(
            f"No approved production card assets directory exists yet: {PRODUCTION_ROOT}. "
            "Structural validation passes; production remains empty and fail-closed."
        )
        return 0

    audited = 0
    failures: list[Path] = []
    unexpected_files: list[Path] = []
    provenance_failures: list[str] = []

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

        validate_provenance(path, provenance.get(path.as_posix()), failures=provenance_failures)

    production_paths = {
        path.as_posix()
        for path in PRODUCTION_ROOT.rglob("*")
        if path.is_file()
    }
    dangling_records = sorted(set(provenance) - production_paths)
    for asset in dangling_records:
        print(f"NOTICE: provenance record has no current production file: {asset}")

    if args.quarantine_invalid:
        for path in [*unexpected_files, *failures]:
            if path.exists():
                destination = _quarantine(path)
                print(f"QUARANTINED: {path} -> {destination}")

    if unexpected_files or failures or provenance_failures:
        print(
            "Invalid production card assets or provenance records remain outside the production contract.",
            file=sys.stderr,
        )
        for failure in provenance_failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    if audited == 0:
        print(
            "Production asset directory is empty: structural contract is valid, "
            "but no card has passed visual/technical approval yet."
        )
    else:
        print(
            f"Production asset contract validated: {audited} asset(s), JPG/JPEG 1024x1536 only, "
            "with asset-level provenance."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
