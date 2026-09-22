from __future__ import annotations

import argparse
from pathlib import Path

from app.game.bosozoku_sprite import process_sprite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the project's original BŌSŌZOKU sprite treatment to a rights-cleared "
            "asset: remove the legacy #FF00FF transparency key and apply a violet tint, "
            "contrast and saturation boost."
        )
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--rights",
        choices=("original", "licensed"),
        required=True,
        help="Rights status for the source material; unknown/unverified material is refused.",
    )
    parser.add_argument("--source-url", default="")
    parser.add_argument("--license", dest="license_name", default="")
    parser.add_argument("--contrast", type=float, default=1.5)
    parser.add_argument("--saturation", type=float, default=1.3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.source.is_file():
        raise SystemExit(f"Source file does not exist: {args.source}")
    if args.rights == "licensed" and (not args.source_url.strip() or not args.license_name.strip()):
        raise SystemExit("Licensed sources require --source-url and --license")
    if args.contrast <= 0 or args.saturation < 0:
        raise SystemExit("contrast must be > 0 and saturation must be >= 0")

    if (
        "assets/production/sprites" in args.destination.as_posix()
        and args.rights not in {"original", "licensed"}
    ):
        raise SystemExit("Only rights-cleared sources may be written to production sprites")

    changed, pixels = process_sprite(
        args.source,
        args.destination,
        contrast=args.contrast,
        saturation=args.saturation,
    )
    print(
        f"Processed {args.source} -> {args.destination}; "
        f"cleared {changed} magenta pixels across {pixels} pixels."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
