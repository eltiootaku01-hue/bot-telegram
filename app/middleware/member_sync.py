from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.social_wake import WakeReason
from app.core.social_wake_store import SocialWakeStore
from app.core.time import utc_now
from app.db.database import Database
from app.db.repositories import MemberRepository


class MemberSyncMiddleware(BaseMiddleware):
    """Keeps member/chat activity fresh and wakes social observation on demand."""

    def __init__(
        self,
        database: Database,
        repository: MemberRepository | None = None,
        wake_store: SocialWakeStore | None = None,
    ) -> None:
        self.database = database
        self.repository = repository or MemberRepository()
        self.wake_store = wake_store or SocialWakeStore()

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
                if (
                    isinstance(event, Message)
                    and not user.is_bot
                    and chat.type in {"group", "supergroup"}
                ):
                    await self.wake_store.request_wake(
                        session,
                        chat.id,
                        utc_now(),
                        reason=WakeReason.EVENT,
                    )
        return await handler(event, data)
