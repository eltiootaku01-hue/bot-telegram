from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, Message

@dataclass(frozen=True, slots=True)
class TelegramAsset:
    file_id: str
    file_unique_id: str
    width: int
    height: int
    mime_type: str
    message_id: int

class TelegramStorageChannel:
    """Uploads normalized WebP files as documents and exposes reusable Telegram IDs."""
    def __init__(self, bot: Bot, chat_id: int) -> None:
        if not chat_id:
            raise ValueError("storage channel chat id must be configured")
        self.bot = bot
        self.chat_id = chat_id

    async def upload(self, asset: Path, *, caption: str = "") -> TelegramAsset:
        message: Message = await self.bot.send_document(
            chat_id=self.chat_id,
            document=FSInputFile(asset),
            caption=caption[:1024] or None,
            disable_content_type_detection=True,
            protect_content=True,
        )
        document = message.document
        if document is None:
            raise RuntimeError("Telegram did not return a document for uploaded asset")
        return TelegramAsset(document.file_id, document.file_unique_id, 0, 0, "image/webp", message.message_id)

    async def delete(self, message_id: int) -> None:
        try:
            await self.bot.delete_message(self.chat_id, message_id)
        except Exception:
            return
