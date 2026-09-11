from datetime import datetime, timedelta

import pytest
from aiogram.types import Chat as TgChat, User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.social_activity import SocialActivityService
from app.core.social_memory import SocialMemory
from app.db.database import Database
from app.db.models import Chat, User, UserChat
from app.db.repositories import MemberRepository


@pytest.fixture
async def session():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as db:
        yield db
    await database.close()


@pytest.mark.asyncio
async def test_observe_ignores_member_presence_for_human_recency(session: AsyncSession):
    now = datetime(2026, 9, 11, 12, 0)
    human_at = now - timedelta(minutes=20)
    chat = Chat(id=-100, type="supergroup", title="community", last_seen_at=now)
    human = User(id=1, first_name="human", is_bot=False, last_seen_at=human_at)
    bot = User(id=2, first_name="bot", is_bot=True, last_seen_at=now)
    session.add_all([chat, human, bot])
    session.add_all([
        UserChat(user_id=1, chat_id=-100, status="member", last_seen_at=human_at),
        UserChat(user_id=2, chat_id=-100, status="member", last_seen_at=now),
    ])
    await session.commit()

    activity = await SocialActivityService().observe(session, -100, now=now)

    assert activity.active_users == 0
    assert activity.last_human_message_at is None
    assert activity.to_snapshot(SocialMemory()).minutes_since_last_message == 0


@pytest.mark.asyncio
async def test_observe_uses_persisted_human_message_time(session: AsyncSession):
    now = datetime(2026, 9, 11, 12, 0)
    human_at = now - timedelta(minutes=20)
    chat = Chat(id=-101, type="supergroup", title="community", last_seen_at=now, last_human_message_at=human_at)
    human = User(id=3, first_name="human", is_bot=False, last_seen_at=human_at)
    session.add_all([chat, human, UserChat(user_id=3, chat_id=-101, status="member", last_seen_at=human_at)])
    await session.commit()

    activity = await SocialActivityService().observe(session, -101, now=now)

    assert activity.active_users == 0
    assert activity.last_human_message_at == human_at
    assert activity.to_snapshot(SocialMemory()).minutes_since_last_message == 20


@pytest.mark.asyncio
async def test_member_touch_does_not_count_non_message_events(session: AsyncSession) -> None:
    repository = MemberRepository()
    user = TgUser(id=10, is_bot=False, first_name="human")
    chat = TgChat(id=-102, type="supergroup", title="community")

    await repository.touch(session, user, chat, is_message=False)
    await repository.touch(session, user, chat, is_message=False)

    link = await session.scalar(select(UserChat).where(
        UserChat.user_id == user.id, UserChat.chat_id == chat.id,
    ))
    stored_chat = await session.get(Chat, chat.id)
    assert link is not None
    assert link.message_count == 0
    assert stored_chat is not None
    assert stored_chat.last_human_message_at is None


@pytest.mark.asyncio
async def test_member_touch_records_real_human_messages(session: AsyncSession) -> None:
    repository = MemberRepository()
    user = TgUser(id=11, is_bot=False, first_name="human")
    chat = TgChat(id=-103, type="supergroup", title="community")

    await repository.touch(session, user, chat, is_message=False)
    assert (await session.get(Chat, chat.id)).last_human_message_at is None

    await repository.touch(session, user, chat, is_message=True)

    link = await session.scalar(select(UserChat).where(
        UserChat.user_id == user.id, UserChat.chat_id == chat.id,
    ))
    stored_chat = await session.get(Chat, chat.id)
    assert link is not None
    assert link.message_count == 1
    assert stored_chat is not None
    assert stored_chat.last_human_message_at is not None
