from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

RARITIES = {"C", "R", "SR", "SSR", "UR"}
DEFAULT_ANIME_ROOT = Path("/data/anime")
DEFAULT_DB_PATH = Path("data/bot.db")

_FIELD_ALIASES = {
    "name": "name", "nombre": "name", "character": "name", "personaje": "name",
    "series": "series", "serie": "series", "anime": "series", "obra": "series",
    "element": "element", "elemento": "element",
    "rarity": "rarity", "rareza": "rarity",
}


@dataclass(frozen=True, slots=True)
class AnimeCardRecord:
    name: str
    series: str
    element: str
    rarity: str
    source_path: str


def _normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch)).strip(" *_`:#")


def _clean_value(value: str) -> str:
    return value.strip().strip("`").strip().strip(" *_`")


def parse_card_markdown(text: str, source_path: str = "") -> AnimeCardRecord:
    """Parse YAML-like front matter or simple Markdown field labels."""
    fields: dict[str, str] = {}
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        lines = lines[1:]
        for index, line in enumerate(lines):
            if line.strip() == "---":
                lines = lines[index + 1:]
                break
            if ":" in line:
                key, value = line.split(":", 1)
                canonical = _FIELD_ALIASES.get(_normalize_key(key))
                if canonical:
                    fields[canonical] = _clean_value(value)

    for line in lines:
        match = re.match(r"^\s*(?:[-*]\s*)?(?:#{1,6}\s*)?(?:\*\*)?([^:]+)(?:\*\*)?\s*:\s*(.+?)\s*$", line)
        if not match:
            continue
        canonical = _FIELD_ALIASES.get(_normalize_key(match.group(1)))
        if canonical and canonical not in fields:
            fields[canonical] = _clean_value(match.group(2))

    missing = [key for key in ("name", "series", "element", "rarity") if not fields.get(key)]
    if missing:
        raise ValueError(f"missing metadata: {', '.join(missing)}")
    rarity = fields["rarity"].upper()
    if rarity not in RARITIES:
        raise ValueError(f"unsupported rarity {rarity!r}; expected one of {sorted(RARITIES)}")
    return AnimeCardRecord(fields["name"][:255], fields["series"][:255], fields["element"][:64], rarity, source_path)


class AnimeCardIndexer:
    """Indexes Markdown metadata and allocates non-reusable edition numbers."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def init(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS anime_card_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    series TEXT NOT NULL,
                    element TEXT NOT NULL,
                    rarity TEXT NOT NULL CHECK (rarity IN ('C','R','SR','SSR','UR')),
                    source_path TEXT NOT NULL UNIQUE,
                    content_sha256 TEXT NOT NULL,
                    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_anime_card_catalog_name ON anime_card_catalog(name);
                CREATE INDEX IF NOT EXISTS idx_anime_card_catalog_rarity ON anime_card_catalog(rarity);
                CREATE TABLE IF NOT EXISTS card_editions (
                    edition_no INTEGER PRIMARY KEY AUTOINCREMENT,
                    catalog_id INTEGER NOT NULL REFERENCES anime_card_catalog(id),
                    name TEXT NOT NULL,
                    rarity TEXT NOT NULL CHECK (rarity IN ('C','R','SR','SSR','UR')),
                    status TEXT NOT NULL CHECK (status IN ('reserved','issued','cancelled')),
                    reserved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    issued_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_card_editions_status ON card_editions(status);
                CREATE INDEX IF NOT EXISTS idx_card_editions_catalog ON card_editions(catalog_id);
            """)

    def scan(self, root: str | Path = DEFAULT_ANIME_ROOT) -> dict[str, int]:
        folder = Path(root)
        if not folder.is_dir():
            raise FileNotFoundError(f"anime Markdown directory does not exist: {folder}")
        stats = {"scanned": 0, "indexed": 0, "updated": 0, "errors": 0}
        for path in sorted(folder.glob("*.md")):
            stats["scanned"] += 1
            try:
                record = parse_card_markdown(path.read_text(encoding="utf-8"), str(path))
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                with sqlite3.connect(self.db_path) as conn:
                    row = conn.execute("SELECT id, content_sha256 FROM anime_card_catalog WHERE source_path = ?", (str(path),)).fetchone()
                    if row is None:
                        conn.execute(
                            "INSERT INTO anime_card_catalog (name, series, element, rarity, source_path, content_sha256) VALUES (?, ?, ?, ?, ?, ?)",
                            (record.name, record.series, record.element, record.rarity, str(path), digest),
                        )
                        stats["indexed"] += 1
                    elif row[1] != digest:
                        conn.execute(
                            "UPDATE anime_card_catalog SET name=?, series=?, element=?, rarity=?, content_sha256=?, indexed_at=CURRENT_TIMESTAMP WHERE id=?",
                            (record.name, record.series, record.element, record.rarity, digest, row[0]),
                        )
                        stats["updated"] += 1
            except (OSError, UnicodeError, ValueError):
                stats["errors"] += 1
        return stats

    def catalog(self, *, rarity: str | None = None) -> list[AnimeCardRecord]:
        query = "SELECT name, series, element, rarity, source_path FROM anime_card_catalog"
        params: tuple[str, ...] = ()
        if rarity:
            rarity = rarity.upper()
            if rarity not in RARITIES:
                raise ValueError(f"unsupported rarity {rarity}")
            query += " WHERE rarity = ?"
            params = (rarity,)
        query += " ORDER BY id"
        with sqlite3.connect(self.db_path) as conn:
            return [AnimeCardRecord(*row) for row in conn.execute(query, params)]

    def reserve_edition(self, catalog_id: int) -> str:
        """Reserve a unique number; delivery requires explicit mark_issued()."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT id, name, rarity FROM anime_card_catalog WHERE id = ?", (catalog_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown catalog id: {catalog_id}")
            cursor = conn.execute(
                "INSERT INTO card_editions (catalog_id, name, rarity, status) VALUES (?, ?, ?, 'reserved')",
                row,
            )
            return f"#{cursor.lastrowid:03d}"

    def mark_issued(self, edition: str) -> None:
        number = int(edition.lstrip("#"))
        with sqlite3.connect(self.db_path) as conn:
            updated = conn.execute(
                "UPDATE card_editions SET status='issued', issued_at=CURRENT_TIMESTAMP WHERE edition_no=? AND status='reserved'",
                (number,),
            ).rowcount
            if updated != 1:
                raise ValueError(f"edition {edition} is not reserved")

    def cancel_reservation(self, edition: str) -> None:
        number = int(edition.lstrip("#"))
        with sqlite3.connect(self.db_path) as conn:
            updated = conn.execute(
                "UPDATE card_editions SET status='cancelled' WHERE edition_no=? AND status='reserved'",
                (number,),
            ).rowcount
            if updated != 1:
                raise ValueError(f"edition {edition} is not reserved")


def scan_anime_folder(root: str | Path = DEFAULT_ANIME_ROOT, db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, int]:
    return AnimeCardIndexer(db_path).scan(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Index anime Markdown card metadata.")
    parser.add_argument("--root", default=str(DEFAULT_ANIME_ROOT))
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()
    print(AnimeCardIndexer(args.db).scan(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
