import re

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message

from app.core.config import get_settings
from app.core.module import BotModule
from app.db.models import MediaAsset
from app.media.library import MediaLibrary
from app.services.requests import DEFAULT_REQUEST_COST, RequestService


class MediaModule(BotModule):
    """Media inbox and fan-request intake; web administration controls the queue."""

    name = "media"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.settings = get_settings()
        self.library = MediaLibrary()
        self.requests = RequestService()

    def setup(self) -> None:
        self.router.message.register(self.request, Command("pedido"))
        self.router.message.register(self.capture_message_photo, F.photo)
        self.router.message.register(self.capture_message_document, F.document)
        self.router.channel_post.register(self.capture_channel_photo, F.photo)
        self.router.channel_post.register(self.capture_channel_document, F.document)

    async def request(self, message: Message) -> None:
        if message.from_user is None:
            return
        raw = (message.text or "").partition(" ")[2].strip()
        if not raw:
            await message.answer(
                f"📝 Usá <code>/pedido personaje + detalle</code>.\n"
                f"Costo provisional: ⭐ {DEFAULT_REQUEST_COST} puntos."
            )
            return
        async with self.database.session() as session:
            result = await self.requests.create_paid(
                session,
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                description=raw,
                points_cost=DEFAULT_REQUEST_COST,
                source_message_id=message.message_id,
            )
            if result is None:
                await message.answer(
                    f"❌ Necesitás ⭐ {DEFAULT_REQUEST_COST} puntos para hacer un pedido."
                )
                return
            request, balance = result
        await message.answer(
            f"📥 <b>Pedido #{request.id} recibido.</b>\n"
            f"⭐ -{DEFAULT_REQUEST_COST} puntos · saldo: {balance}\n"
            "El pedido quedó en la cola privada para revisión."
        )

    def _allowed_storage_chat(self, message: Message) -> bool:
        return bool(self.settings.media_storage_chat_id) and message.chat.id == self.settings.media_storage_chat_id

    @staticmethod
    def _tags_from_caption(caption: str | None) -> str:
        tags = re.findall(r"#[\wáéíóúüñ-]+", caption or "", flags=re.IGNORECASE)
        return ",".join(tag[1:].lower() for tag in tags)

    async def capture_message_photo(self, message: Message) -> None:
        if not self._allowed_storage_chat(message) or not message.photo:
            return
        photo = message.photo[-1]
        await self._store(photo.file_id, photo.file_unique_id, message, "photo")

    async def capture_message_document(self, message: Message) -> None:
        if not self._allowed_storage_chat(message) or not message.document:
            return
        if not (message.document.mime_type or "").startswith("image/"):
            return
        await self._store(message.document.file_id, message.document.file_unique_id, message, "document")

    async def capture_channel_photo(self, message: Message) -> None:
        if not self._allowed_storage_chat(message) or not message.photo:
            return
        photo = message.photo[-1]
        await self._store(photo.file_id, photo.file_unique_id, message, "photo")

    async def capture_channel_document(self, message: Message) -> None:
        if not self._allowed_storage_chat(message) or not message.document:
            return
        if not (message.document.mime_type or "").startswith("image/"):
            return
        await self._store(message.document.file_id, message.document.file_unique_id, message, "document")

    async def _store(self, file_id: str, unique_id: str, message: Message, media_type: str) -> None:
        async with self.database.session() as session:
            existing = await self.library.find_by_file_id(session, file_id)
            if existing is not None:
                return
            session.add(
                MediaAsset(
                    telegram_file_id=file_id,
                    telegram_unique_id=unique_id,
                    source_chat_id=message.chat.id,
                    source_message_id=message.message_id,
                    media_type=media_type,
                    tags=self._tags_from_caption(message.caption),
                )
            )
            await session.commit()
