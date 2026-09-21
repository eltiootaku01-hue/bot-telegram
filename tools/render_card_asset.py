from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.assets import resolve_asset
from app.game.art_progression import art_prompt_spec
from app.game.card_art_assets import card_asset_path, validate_card_asset
from app.game.cards import CardVariant
from app.game.catalog import get_character


DEFAULT_MAX_ATTEMPTS = 100
DEFAULT_TIMEOUT_SECONDS = 600


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _command_for(template: str, *, prompt_file: Path, output: Path) -> list[str]:
    rendered = template.format(
        prompt_file=str(prompt_file),
        output=str(output),
    )
    return shlex.split(rendered, posix=False)


def render_card_asset(
    *,
    character_id: str,
    variant: CardVariant,
    seed: str,
    generator_command: str,
    output: Path,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    if not 1 <= max_attempts <= DEFAULT_MAX_ATTEMPTS:
        raise ValueError("max_attempts must be between 1 and 100")

    character = get_character(character_id)
    prompt = art_prompt_spec(
        character_name=character.name,
        anime=character.anime,
        character_id=character.id,
        level=25,
        card_tier=character.card_tier,
        variant=variant.value,
        popularity_score=character.popularity_score,
        power_score=character.power_score,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "character_id": character_id,
        "variant": variant.value,
        "seed": seed,
        "output": str(output),
        "attempts": [],
        "max_attempts": max_attempts,
        "started_at": _now_iso(),
    }

    with tempfile.TemporaryDirectory(prefix="card-render-") as temp_dir:
        prompt_file = Path(temp_dir) / "prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")

        for attempt in range(1, max_attempts + 1):
            attempt_record: dict[str, object] = {
                "attempt": attempt,
                "started_at": _now_iso(),
            }
            try:
                command = _command_for(
                    generator_command,
                    prompt_file=prompt_file,
                    output=output,
                )
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                attempt_record["returncode"] = completed.returncode
                attempt_record["stdout_tail"] = completed.stdout[-1000:]
                attempt_record["stderr_tail"] = completed.stderr[-1000:]

                if completed.returncode != 0:
                    attempt_record["result"] = "generator_failed"
                else:
                    validation = validate_card_asset(output)
                    attempt_record["validation"] = {
                        "valid": validation.valid,
                        "width": validation.width,
                        "height": validation.height,
                        "size_bytes": validation.size_bytes,
                        "reason": validation.reason,
                    }
                    if validation.valid:
                        attempt_record["result"] = "accepted"
                        attempt_record["finished_at"] = _now_iso()
                        cast_attempts = manifest["attempts"]
                        assert isinstance(cast_attempts, list)
                        cast_attempts.append(attempt_record)
                        manifest["finished_at"] = _now_iso()
                        manifest["status"] = "accepted"
                        return manifest
                    attempt_record["result"] = "invalid_asset"
            except (OSError, subprocess.SubprocessError) as exc:
                attempt_record["result"] = "execution_error"
                attempt_record["error"] = str(exc)

            attempt_record["finished_at"] = _now_iso()
            cast_attempts = manifest["attempts"]
            assert isinstance(cast_attempts, list)
            cast_attempts.append(attempt_record)

    manifest["finished_at"] = _now_iso()
    manifest["status"] = "failed"
    raise RuntimeError(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render and validate one collectible card asset."
    )
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--variant", choices=[item.value for item in CardVariant], required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Final JPEG path; defaults to the standard repository asset path.",
    )
    parser.add_argument(
        "--generator-command",
        required=True,
        help="Command template containing {prompt_file} and {output} placeholders.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    args = parser.parse_args()

    output = args.output or Path(card_asset_path(args.character_id, args.variant))
    result = render_card_asset(
        character_id=args.character_id,
        variant=CardVariant(args.variant),
        seed=args.seed,
        generator_command=args.generator_command,
        output=output,
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Stored: {resolve_asset(str(output)) or output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
