from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.config import Settings


class ChatAccessMiddleware(BaseMiddleware):
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
        callback = update.callback_query
        if callback is not None and callback.message is not None:
            message = callback.message
            actor = callback.from_user
        else:
            message = update.message or update.edited_message
            actor = message.from_user if message is not None else None

        if message is None:
            return False

        chat = message.chat
        return self.settings.is_chat_allowed(
            chat.id,
            chat.type,
            actor.id if actor is not None else None,
        )
