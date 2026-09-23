from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import TelegramObject

from app.core.identity import BotIdentity


class BotIdentityFilter(Filter):
    """Route a handler exclusively to the Telegram bot identity that owns it."""

    def __init__(self, identity: BotIdentity, bot_ids: dict[BotIdentity, int]) -> None:
        self.identity = identity
        self.bot_ids = bot_ids

    async def __call__(self, event: TelegramObject, bot) -> bool:
        return bot.id == self.bot_ids[self.identity]
