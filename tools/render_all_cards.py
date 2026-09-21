from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.game.cards import CardVariant
from app.game.catalog import CHARACTERS
from app.game.card_art_assets import card_asset_path
from tools.render_card_asset import DEFAULT_MAX_ATTEMPTS, DEFAULT_TIMEOUT_SECONDS, render_card_asset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render all base character card variants and continue after failures."
    )
    parser.add_argument("--generator-command", required=True)
    parser.add_argument(
        "--character-id",
        action="append",
        dest="character_ids",
        help="Render only the listed character. Repeat for multiple characters.",
    )
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
    )
    args = parser.parse_args()

    character_ids = (
        tuple(args.character_ids)
        if args.character_ids
        else tuple(sorted(CHARACTERS))
    )

    report: dict[str, object] = {
        "max_attempts_per_asset": args.max_attempts,
        "timeout_seconds_per_attempt": args.timeout_seconds,
        "requested_characters": len(character_ids),
        "variants_per_character": 2,
        "results": [],
    }

    for character_id in character_ids:
        if character_id not in CHARACTERS:
            report["results"].append(
                {
                    "character_id": character_id,
                    "status": "skipped_unknown_character",
                }
            )
            continue

        for variant in (CardVariant.NORMAL, CardVariant.SHINY):
            output = args.output_root / card_asset_path(character_id, variant.value)
            seed = f"batch:{character_id}:{variant.value}:v1"
            try:
                result = render_card_asset(
                    character_id=character_id,
                    variant=variant,
                    seed=seed,
                    generator_command=args.generator_command,
                    output=output,
                    max_attempts=args.max_attempts,
                    timeout_seconds=args.timeout_seconds,
                )
                report["results"].append(result)
                print(f"ACCEPTED {character_id} {variant.value}: {output}")
            except RuntimeError as exc:
                report["results"].append(
                    {
                        "character_id": character_id,
                        "variant": variant.value,
                        "status": "failed_after_retry_limit",
                        "output": str(output),
                        "error": str(exc),
                    }
                )
                print(
                    f"SKIPPED {character_id} {variant.value}: "
                    f"failed after {args.max_attempts} attempts"
                )

    accepted = sum(
        1
        for item in report["results"]
        if isinstance(item, dict) and item.get("status") == "accepted"
    )
    failed = sum(
        1
        for item in report["results"]
        if isinstance(item, dict) and item.get("status") == "failed_after_retry_limit"
    )
    report["accepted"] = accepted
    report["failed"] = failed

    report_path = args.output_root / "assets/waifus/render_batch_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Report: {report_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
