from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.core.config import get_settings
from app.db.database import Database
from app.services.anime_import import import_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a local, manually verified anime/manga JSON catalog into SQLite."
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a UTF-8 JSON file following docs/reference/ANIME_METADATA_IMPORT_FORMAT.md",
    )
    return parser.parse_args()


async def run(path: Path) -> int:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        await database.create_schema()
        async with database.session(write=True) as session:
            report = await import_file(session, path)
        print(
            "Import completed: "
            f"{report.works_written} works, "
            f"{report.characters_written} characters."
        )
        return 0
    finally:
        await database.close()


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args.path))
    except ValueError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
