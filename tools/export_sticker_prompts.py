from __future__ import annotations

import argparse
from pathlib import Path

from app.stickers.catalog import STICKER_CATALOG, sticker_prompt


def build_markdown() -> str:
    lines = [
        "# Sticker prompt export",
        "",
        "Generated from app.stickers.catalog.STICKER_CATALOG.",
        "",
    ]
    for spec in STICKER_CATALOG:
        lines.extend(
            [
                f"## {spec.key}",
                f"- Identity: {spec.identity.value}",
                f"- Intent: {spec.intent.value}",
                f"- Text: {spec.text or '(none)'}",
                "",
                sticker_prompt(spec),
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export authored Telegram sticker prompts.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/stickers/generated/STICKER_PROMPTS.md"),
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_markdown(), encoding="utf-8")
    print(f"Wrote {len(STICKER_CATALOG)} sticker prompts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
