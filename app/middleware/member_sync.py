from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message, TelegramObject

from app.core.social_wake import WakeReason
from app.core.time import utc_now
from app.db.database import Database
from app.db.repositories import MemberRepository


class MemberSyncMiddleware(BaseMiddleware):
    """Keeps member/chat identity, membership and activity fresh."""

    def __init__(
        self,
        database: Database,
        repository: MemberRepository | None = None,
        wake_store=None,
    ) -> None:
        self.database = database
        self.repository = repository or MemberRepository()
        self.wake_store = wake_store

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[object]],
        event: TelegramObject,
        data: dict,
    ) -> object:
        if isinstance(event, ChatMemberUpdated):
            await self._sync_membership_event(event)
            return await handler(event, data)

        user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)
        if isinstance(event, CallbackQuery) and event.message is not None:
            chat = getattr(event.message, "chat", chat)
        if isinstance(event, Message):
            chat = event.chat

        if user is not None and chat is not None:
            is_message = isinstance(event, Message)
            async with self.database.session() as session:
                await self.repository.touch(
                    session,
                    user,
                    chat,
                    is_message=is_message,
                    commit=False,
                )
                if (
                    is_message
                    and not user.is_bot
                    and chat.type in {"group", "supergroup"}
                ):
                    if self.wake_store is None:
                        from app.core.social_wake_store import SocialWakeStore

                        wake_store = SocialWakeStore()
                    else:
                        wake_store = self.wake_store
                    await wake_store.request_wake(
                        session,
                        chat.id,
                        utc_now(),
                        reason=WakeReason.EVENT,
                        commit=False,
                    )
        return await handler(event, data)

    async def _sync_membership_event(self, event: ChatMemberUpdated) -> None:
        member_user = event.new_chat_member.user
        status = getattr(event.new_chat_member.status, "value", event.new_chat_member.status)
        if status == "restricted":
            status = "member" if getattr(event.new_chat_member, "is_member", False) else "left"
        async with self.database.session() as session:
            await self.repository.set_membership(
                session,
                member_user,
                event.chat,
                str(status),
                commit=False,
            )
