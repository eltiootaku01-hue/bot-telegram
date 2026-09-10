from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.database import Database
from app.db.repositories import MemberRepository


class MemberSyncMiddleware(BaseMiddleware):
    """Keeps the local member/chat registry fresh without involving the AI layer."""

    def __init__(self, database: Database, repository: MemberRepository | None = None) -> None:
        self.database = database
        self.repository = repository or MemberRepository()

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)
        if user is not None and chat is not None:
            async with self.database.sessions() as session:
                await self.repository.touch(session, user, chat)
        return await handler(event, data)
