import re

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from app.core.config import get_settings
from app.core.module import BotModule
from app.db.database import Database
from app.db.models import MediaAsset


class MediaModule(BotModule):
    """Image inbox: one private Telegram chat becomes the bot's asset library."""

    name = "media"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.settings = get_settings()

    def setup(self) -> None:
        self.router.message.register(self.request, Command("pedido"))
        self.router.channel_post.register(self.capture_channel_photo, F.photo)
        self.router.channel_post.register(self.capture_channel_document, F.document)

    async def request(self, message: Message) -> None:
        await message.answer(
            "📥 Pedido recibido. La cola de pedidos e imágenes se conectará a la biblioteca. "
            "La gestión completa quedará en la web privada."
        )

    def _allowed_storage_chat(self, message: Message) -> bool:
        return bool(self.settings.media_storage_chat_id) and message.chat.id == self.settings.media_storage_chat_id

    @staticmethod
    def _tags_from_caption(caption: str | None) -> str:
        tags = re.findall(r"#[\wáéíóúüñ-]+", caption or "", flags=re.IGNORECASE)
        return ",".join(tag[1:].lower() for tag in tags)

    async def capture_channel_photo(self, message: Message) -> None:
        if not self._allowed_storage_chat(message) or not message.photo:
            return
        photo = message.photo[-1]
        await self._store(
            file_id=photo.file_id,
            unique_id=photo.file_unique_id,
            message=message,
            tags=self._tags_from_caption(message.caption),
        )

    async def capture_channel_document(self, message: Message) -> None:
        if not self._allowed_storage_chat(message) or not message.document:
            return
        if not (message.document.mime_type or "").startswith("image/"):
            return
        await self._store(
            file_id=message.document.file_id,
            unique_id=message.document.file_unique_id,
            message=message,
            tags=self._tags_from_caption(message.caption),
        )

    async def _store(
        self,
        *,
        file_id: str,
        unique_id: str,
        message: Message,
        tags: str,
    ) -> None:
        async with self.database.session() as session:
            existing = await session.scalar(
                select(MediaAsset).where(MediaAsset.telegram_file_id == file_id)
            )
            if existing is None:
                session.add(
                    MediaAsset(
                        telegram_file_id=file_id,
                        telegram_unique_id=unique_id,
                        source_chat_id=message.chat.id,
                        source_message_id=message.message_id,
                        tags=tags,
                    )
                )
                await session.commit()
