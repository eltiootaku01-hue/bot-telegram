from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.config import Settings


class ChatAccessMiddleware(BaseMiddleware):
    """Fail-closed Telegram chat gate before member sync, routing or module work."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[object]],
        event: TelegramObject,
        data: dict,
    ) -> object | None:
        update = data.get("event_update")
        if not isinstance(update, Update):
            update = event if isinstance(event, Update) else None

        if update is None or self._is_allowed(update):
            return await handler(event, data)
        return None

    def _is_allowed(self, update: Update) -> bool:
        message = update.message or update.edited_message
        if message is None:
            callback = update.callback_query
            message = callback.message if callback is not None else None

        if message is None:
            return False

        user = message.from_user
        return self.settings.is_chat_allowed(
            message.chat.id,
            message.chat.type,
            user.id if user is not None else None,
        )
