from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path

import imagehash
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import Database
from app.db.models import CardDefinition
from .image_processor import ImageProcessor
from .storage_channel import TelegramStorageChannel

logger = logging.getLogger(__name__)
RARITIES = {"C", "R", "SR", "SSR", "UR"}

def _csv_ints(value: str) -> frozenset[int]:
    result = set()
    for raw in value.split(","):
        raw = raw.strip()
        if raw:
            try:
                result.add(int(raw))
            except ValueError:
                continue
    return frozenset(result)

def parse_metadata(caption: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in caption.split("|", 2)]
    if len(parts) != 3 or not all(parts):
        raise ValueError("caption must be: /ingest Name | Anime Series | Rarity")
    name, anime, rarity = parts
    rarity = rarity.upper()
    if rarity not in RARITIES:
        raise ValueError("rarity must be one of C, R, SR, SSR, UR")
    if len(name) > 255 or len(anime) > 255:
        raise ValueError("name and anime_series are limited to 255 characters")
    return name, anime, rarity

def phash_similarity(left: str, right: str) -> float:
    a, b = imagehash.hex_to_hash(left), imagehash.hex_to_hash(right)
    return 1.0 - (a - b) / max(len(a.hash), 1)

class VaultAdmin:
    """Admin-only Telegram ingestion service with DB-backed perceptual deduplication."""
    def __init__(self, database: Database, storage: TelegramStorageChannel, processor: ImageProcessor) -> None:
        self.database = database
        self.storage = storage
        self.processor = processor
        self._lock = asyncio.Lock()

    async def _is_duplicate(self, phash: str) -> tuple[bool, float]:
        async with self.database.session() as session:
            rows = list(await session.scalars(select(CardDefinition.phash).where(CardDefinition.phash.is_not(None))))
        best = 0.0
        for existing in rows:
            if existing:
                best = max(best, phash_similarity(phash, str(existing)))
        return best > 0.90, best

    async def ingest(self, source: Path, *, name: str, anime_series: str, rarity: str) -> CardDefinition:
        async with self._lock:
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            processed = self.processor.process(source, output_name=digest[:32])
            duplicate, similarity = await self._is_duplicate(processed.phash)
            if duplicate:
                processed.path.unlink(missing_ok=True)
                raise ValueError(f"asset rejected as duplicate (similarity={similarity:.1%})")
            telegram_asset = await self.storage.upload(processed.path, caption=f"{name} · {anime_series} · {rarity}")
            card_id = f"asset-{digest[:32]}"
            try:
                async with self.database.session(write=True) as session:
                    if await session.get(CardDefinition, card_id) is not None:
                        raise ValueError(f"card_id already exists: {card_id}")
                    definition = CardDefinition(
                        id=card_id, card_code=None, character_id=card_id, character_name=name,
                        anime_origin=anime_series, rarity=rarity, image_url="", asset_path=str(processed.path),
                        thumbnail_path=None, asset_sha256=digest, source_provider="telegram_storage_channel",
                        collection_points=0, coin_value=0, telegram_protected=True,
                        telegram_file_id=telegram_asset.file_id, telegram_file_unique_id=telegram_asset.file_unique_id,
                        asset_width=processed.width, asset_height=processed.height,
                        asset_mime_type=processed.mime_type, phash=processed.phash,
                    )
                    session.add(definition)
                    await session.flush()
            except Exception:
                await self.storage.delete(telegram_asset.message_id)
                processed.path.unlink(missing_ok=True)
                raise
            return definition

def _media_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    if message.document and (message.document.mime_type or "").startswith("image/"):
        return message.document.file_id
    return None

def build_router(admin: VaultAdmin, bot: Bot, admin_user_ids: frozenset[int]) -> Router:
    router = Router(name="vault_admin")
    @router.message(Command("ingest"))
    async def ingest(message: Message) -> None:
        if not message.from_user or message.from_user.id not in admin_user_ids:
            return
        file_id = _media_file_id(message)
        if file_id is None:
            await message.answer("Adjuntá una imagen con: /ingest Nombre | Anime | Rareza")
            return
        try:
            caption = (message.caption or "").removeprefix("/ingest").strip()
            name, anime, rarity = parse_metadata(caption)
            source = Path(tempfile.gettempdir()) / f"vault-ingest-{message.chat.id}-{message.message_id}.bin"
            await bot.download(file_id, destination=source)
            definition = await admin.ingest(source, name=name, anime_series=anime, rarity=rarity)
            source.unlink(missing_ok=True)
            await message.answer(f"✅ Indexada {definition.id}\nTelegram file_id: <code>{definition.telegram_file_id}</code>")
        except ValueError as exc:
            await message.answer(f"❌ {exc}")
        except Exception:
            logger.exception("vault asset ingestion failed")
            await message.answer("❌ No se pudo indexar el asset. Revisá los logs del administrador.")
    @router.message(F.photo | F.document)
    async def media_help(message: Message) -> None:
        if message.from_user and message.from_user.id in admin_user_ids:
            await message.answer("Para indexar: /ingest Nombre | Anime | Rareza en el caption.")
    return router

async def run() -> None:
    settings = get_settings()
    token = os.getenv("VAULT_ADMIN_BOT_TOKEN", "").strip()
    storage_chat_id = int(os.getenv("VAULT_STORAGE_CHAT_ID", "0") or 0)
    admin_ids = _csv_ints(os.getenv("VAULT_ADMIN_USER_IDS", ""))
    if not token or not admin_ids or not storage_chat_id:
        raise RuntimeError("VAULT_ADMIN_BOT_TOKEN, VAULT_STORAGE_CHAT_ID and VAULT_ADMIN_USER_IDS are required")
    bot = Bot(token)
    database = Database(settings.database_url)
    await database.create_schema()
    admin = VaultAdmin(database, TelegramStorageChannel(bot, storage_chat_id), ImageProcessor(settings.card_asset_root))
    dp = Dispatcher()
    dp.include_router(build_router(admin, bot, admin_ids))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await database.close()

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())

if __name__ == "__main__":
    main()
