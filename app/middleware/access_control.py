from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.config import Settings


class ChatAccessMiddleware(BaseMiddleware):
    """Fail-closed access gate with one audited Chie onboarding exception."""

    BOOTSTRAP_FLAG = "chat_access_bootstrap"

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

        if await self._allow_chie_bootstrap(update, data):
            data[self.BOOTSTRAP_FLAG] = True
            return await handler(event, data)

        return None

    def _is_allowed(self, update: Update) -> bool:
        membership = (
            update.chat_member
            or update.chat_join_request
            or update.my_chat_member
        )
        if membership is not None:
            return self.settings.is_chat_allowed(
                membership.chat.id,
                membership.chat.type,
            )

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

    async def _allow_chie_bootstrap(self, update: Update, data: dict) -> bool:
        """Allow only the exact onboarding command from a real group admin."""
        message = update.message
        if message is None or message.chat.type not in {"group", "supergroup"}:
            return False
        if message.from_user is None or not message.text:
            return False

        command = message.text.strip().split(maxsplit=1)[0].casefold()
        if command.split("@", 1)[0] != "/configurar":
            return False

        bot = data.get("bot")
        if bot is None:
            return False

        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        except Exception:
            return False
        status = getattr(member.status, "value", member.status)
        return status in {"administrator", "creator"}
