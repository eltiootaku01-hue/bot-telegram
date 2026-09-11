from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.social_activity import SocialActivityService
from app.core.social_memory import SocialMemory
from app.db.database import Database
from app.db.models import Chat, User, UserChat


@pytest.fixture
async def session():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as db:
        yield db
    await database.close()


@pytest.mark.asyncio
async def test_observe_ignores_recent_bot_activity_for_human_recency(session: AsyncSession):
    now = datetime(2026, 9, 11, 12, 0)
    chat = Chat(id=-100, type="supergroup", title="community", last_seen_at=now)
    human = User(id=1, first_name="human", is_bot=False, last_seen_at=now - timedelta(minutes=20))
    bot = User(id=2, first_name="bot", is_bot=True, last_seen_at=now)
    session.add_all([chat, human, bot])
    session.add_all([
        UserChat(user_id=1, chat_id=-100, status="member", last_seen_at=now - timedelta(minutes=20)),
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
