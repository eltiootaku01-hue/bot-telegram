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
            return self.settings.is_chat_allowed(
                callback.message.chat.id,
                callback.message.chat.type,
                callback.from_user.id if callback.from_user is not None else None,
            )

        message = update.message or update.edited_message
        if message is not None:
            user = message.from_user
            return self.settings.is_chat_allowed(
                message.chat.id,
                message.chat.type,
                user.id if user is not None else None,
            )

        member_update = update.chat_member
        if member_update is not None:
            return self.settings.is_chat_allowed(
                member_update.chat.id,
                member_update.chat.type,
                member_update.from_user.id if member_update.from_user is not None else None,
            )

        my_member_update = update.my_chat_member
        if my_member_update is not None:
            return self.settings.is_chat_allowed(
                my_member_update.chat.id,
                my_member_update.chat.type,
                my_member_update.from_user.id if my_member_update.from_user is not None else None,
            )

        join_request = update.chat_join_request
        if join_request is not None:
            return self.settings.is_chat_allowed(
                join_request.chat.id,
                join_request.chat.type,
                join_request.from_user.id if join_request.from_user is not None else None,
            )

        return False
