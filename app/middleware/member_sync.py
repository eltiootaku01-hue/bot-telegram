from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.db.database import Database
from app.db.repositories import MemberRepository


class MemberSyncMiddleware(BaseMiddleware):
    """Keeps member/chat activity fresh without involving the AI layer."""

    def __init__(self, database: Database, repository: MemberRepository | None = None) -> None:
        self.database = database
        self.repository = repository or MemberRepository()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[object]],
        event: TelegramObject,
        data: dict,
    ) -> object:
        user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)
        if isinstance(event, CallbackQuery) and event.message is not None:
            chat = getattr(event.message, "chat", chat)
        if isinstance(event, Message):
            chat = event.chat

        if user is not None and chat is not None:
            async with self.database.session() as session:
                await self.repository.touch(session, user, chat)
        return await handler(event, data)
