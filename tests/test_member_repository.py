import pytest
from aiogram.types import Chat as TgChat, User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Chat, User, UserChat
from app.db.repositories import MemberRepository


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


def telegram_user() -> TgUser:
    return TgUser(id=7, is_bot=False, first_name="Test", username="tester")


def telegram_chat() -> TgChat:
    return TgChat(id=-100, type="supergroup", title="Community")


@pytest.mark.asyncio
async def test_touch_creates_identity_and_counts_first_message(session):
    repo = MemberRepository()
    await repo.touch(session, telegram_user(), telegram_chat())

    assert await session.get(User, 7) is not None
    assert await session.get(Chat, -100) is not None
    link = await session.scalar(select(UserChat).where(UserChat.user_id == 7, UserChat.chat_id == -100))
    assert link is not None
    assert link.message_count == 1


@pytest.mark.asyncio
async def test_touch_increments_message_count_atomically(session):
    repo = MemberRepository()
    user = telegram_user()
    chat = telegram_chat()
    await repo.touch(session, user, chat)
    await repo.touch(session, user, chat)
    await repo.touch(session, user, chat)

    link = await session.scalar(select(UserChat).where(UserChat.user_id == 7, UserChat.chat_id == -100))
    assert link is not None
    assert link.message_count == 3
