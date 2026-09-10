from datetime import datetime

from aiogram.types import Chat as TgChat, User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, User, UserChat


class MemberRepository:
    """Persists Telegram members and their membership/activity per chat."""

    async def touch(self, session: AsyncSession, user: TgUser, chat: TgChat) -> None:
        now = datetime.utcnow()
        db_user = await session.get(User, user.id)
        if db_user is None:
            db_user = User(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
                is_bot=user.is_bot,
                created_at=now,
                last_seen_at=now,
            )
            session.add(db_user)
        else:
            db_user.username = user.username
            db_user.first_name = user.first_name
            db_user.last_name = user.last_name
            db_user.language_code = user.language_code
            db_user.last_seen_at = now

        db_chat = await session.get(Chat, chat.id)
        if db_chat is None:
            db_chat = Chat(
                id=chat.id,
                type=chat.type,
                title=chat.title,
                username=chat.username,
                created_at=now,
                last_seen_at=now,
            )
            session.add(db_chat)
        else:
            db_chat.type = chat.type
            db_chat.title = chat.title
            db_chat.username = chat.username
            db_chat.last_seen_at = now

        link = await session.scalar(
            select(UserChat).where(UserChat.user_id == user.id, UserChat.chat_id == chat.id)
        )
        if link is None:
            session.add(UserChat(user_id=user.id, chat_id=chat.id, first_seen_at=now, last_seen_at=now))
        else:
            link.last_seen_at = now

        await session.commit()
