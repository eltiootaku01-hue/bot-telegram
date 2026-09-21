from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message

from app.characters.models import CharacterIntent
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.stickers.catalog import sticker_for


class StickerService:
    """Resolve authored sticker keys and optionally send configured Telegram stickers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def file_id_for(
        self,
        identity: BotIdentity,
        intent: CharacterIntent,
        *,
        roll: int = 0,
    ) -> str | None:
        spec = sticker_for(identity, intent, roll=roll)
        if spec is None:
            return None
        return self.settings.telegram_sticker_file_ids.get(spec.telegram_lookup_key)

    async def send_if_configured(
        self,
        bot: Bot,
        message: Message,
        identity: BotIdentity,
        intent: CharacterIntent,
        *,
        roll: int = 0,
    ) -> bool:
        """Send a sticker only when its file_id is explicitly configured."""
        file_id = self.file_id_for(identity, intent, roll=roll)
        if not file_id:
            return False
        await bot.send_sticker(message.chat.id, sticker=file_id)
        return True
