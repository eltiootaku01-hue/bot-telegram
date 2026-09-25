from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sqlite3
from pathlib import Path
from typing import Callable

import requests
from PIL import Image, ImageOps

from src.admin.perceptual_hash import is_perceptual_duplicate

logger = logging.getLogger(__name__)

OUTPUT_SIZE = (512, 768)
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_MAX_DISTANCE = 4


class CardVault:
    """Two-phase local/remote card state store."""

    def __init__(self, db_path: str = "data/card_vault.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    card_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    series TEXT NOT NULL,
                    rarity TEXT NOT NULL,
                    phash TEXT NOT NULL,
                    telegram_file_id TEXT NULL,
                    discord_attachment_url TEXT NULL,
                    status TEXT NOT NULL DEFAULT 'PROCESSED_LOCAL',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
            if "status" not in columns:
                conn.execute(
                    "ALTER TABLE cards ADD COLUMN status TEXT NOT NULL DEFAULT 'PROCESSED_LOCAL'"
                )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_phash ON cards(phash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status)")
            conn.commit()

    def existing_hashes(self) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            return [row[0] for row in conn.execute("SELECT phash FROM cards")]

    def insert_local(self, *, card_id: str, name: str, series: str, rarity: str, phash: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cards
                    (card_id, name, series, rarity, phash, status)
                VALUES (?, ?, ?, ?, ?, 'PROCESSED_LOCAL')
                """,
                (card_id, name, series, rarity, phash),
            )
            conn.commit()

    def mark_remote(self, card_id: str, telegram_file_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE cards
                SET telegram_file_id = ?, status = 'STORED_REMOTE'
                WHERE card_id = ?
                """,
                (telegram_file_id, card_id),
            )
            conn.commit()

    def get(self, card_id: str) -> tuple | None:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                """
                SELECT card_id, name, series, rarity, phash,
                       telegram_file_id, status
                FROM cards WHERE card_id = ?
                """,
                (card_id,),
            ).fetchone()


def normalize_image(source: Path, destination: Path) -> None:
    """Convert to WebP 512x768 while preserving aspect ratio via center crop."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        normalized = ImageOps.fit(
            rgb,
            OUTPUT_SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        normalized.save(destination, "WEBP", quality=90, method=6)


def content_card_id(normalized_path: Path) -> str:
    digest = hashlib.sha256(normalized_path.read_bytes()).hexdigest()
    return f"card_{digest[:32]}"


def default_metadata(path: Path) -> tuple[str, str, str]:
    return path.stem.replace("_", " ").strip().title(), "General Anime", "SSR"


def telegram_uploader(bot_token: str, chat_id: int) -> Callable[[Path, str], str]:
    """Build the phase-2 Telegram uploader."""
    def upload(normalized_path: Path, card_id: str) -> str:
        endpoint = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        with normalized_path.open("rb") as handle:
            response = requests.post(
                endpoint,
                data={"chat_id": str(chat_id), "caption": card_id},
                files={"document": (normalized_path.name, handle, "image/webp")},
                timeout=30,
            )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")
        file_id = payload.get("result", {}).get("document", {}).get("file_id")
        if not file_id:
            raise RuntimeError("Telegram response did not contain document.file_id")
        return str(file_id)
    return upload


def ingest_folder(
    input_dir: str,
    *,
    db_path: str = "data/card_vault.db",
    max_distance: int = DEFAULT_MAX_DISTANCE,
    dry_run: bool = False,
    remote_uploader: Callable[[Path, str], str] | None = None,
) -> dict[str, int]:
    if max_distance < 0:
        raise ValueError("max_distance must be non-negative")
    folder = Path(input_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    vault = CardVault(db_path)
    vault.init()
    existing_hashes = vault.existing_hashes()
    normalized_dir = folder / ".normalized"
    stats = {"processed_local": 0, "stored_remote": 0, "skipped": 0, "errors": 0}

    images = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES
    )

    for source in images:
        try:
            normalized = normalized_dir / f"{source.stem}.webp"
            normalize_image(source, normalized)

            with Image.open(normalized) as normalized_image:
                from imagehash import phash
                current_phash = str(phash(normalized_image))

            duplicate, distance = is_perceptual_duplicate(
                current_phash, existing_hashes, max_distance
            )
            if duplicate:
                logger.info("Skipping %s: pHash distance=%s", source, distance)
                stats["skipped"] += 1
                continue

            card_id = content_card_id(normalized)
            name, series, rarity = default_metadata(source)

            if dry_run:
                stats["processed_local"] += 1
                continue

            vault.insert_local(
                card_id=card_id,
                name=name,
                series=series,
                rarity=rarity,
                phash=current_phash,
            )
            existing_hashes.append(current_phash)
            stats["processed_local"] += 1

            if remote_uploader is not None:
                file_id = remote_uploader(normalized, card_id)
                vault.mark_remote(card_id, file_id)
                stats["stored_remote"] += 1
        except Exception:
            logger.exception("Failed to ingest %s", source)
            stats["errors"] += 1

    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vault Asset Ingestion")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)
    parser.add_argument("--input-dir", default="assets/raw_cards")
    parser.add_argument("--db-path", default="data/card_vault.db")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args()

    if args.dry_run:
        uploader = None
    else:
        token = os.getenv("TELEGRAM_ASSET_BOT_TOKEN")
        raw_chat_id = os.getenv("TELEGRAM_ASSET_CHAT_ID")
        if not token or not raw_chat_id:
            logger.error("Telegram credentials are required unless --dry-run is used")
            return 2
        try:
            uploader = telegram_uploader(token, int(raw_chat_id))
        except ValueError:
            logger.error("TELEGRAM_ASSET_CHAT_ID must be an integer")
            return 2

    stats = ingest_folder(
        args.input_dir,
        db_path=args.db_path,
        max_distance=args.max_distance,
        dry_run=args.dry_run,
        remote_uploader=uploader,
    )
    logger.info("Ingestion finished: %s", stats)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
