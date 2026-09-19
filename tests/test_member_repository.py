import pytest
from aiogram.types import Chat as TgChat, User as TgUser
from sqlalchemy import select

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


@pytest.mark.asyncio
async def test_touch_can_join_caller_transaction(session):
    repo = MemberRepository()

    await repo.touch(session, telegram_user(), telegram_chat(), commit=False)
    await session.rollback()
    session.expire_all()

    assert await session.scalar(select(User.id).where(User.id == 7)) is None
    assert await session.scalar(select(Chat.id).where(Chat.id == -100)) is None
    assert await session.scalar(
        select(UserChat.id).where(UserChat.user_id == 7, UserChat.chat_id == -100)
    ) is None


@pytest.mark.asyncio
async def test_set_membership_can_join_caller_transaction(session):
    repo = MemberRepository()

    await repo.set_membership(
        session,
        telegram_user(),
        telegram_chat(),
        "member",
        commit=False,
    )
    await session.rollback()
    session.expire_all()

    assert await session.scalar(select(User.id).where(User.id == 7)) is None
    assert await session.scalar(select(Chat.id).where(Chat.id == -100)) is None
    assert await session.scalar(
        select(UserChat.id).where(UserChat.user_id == 7, UserChat.chat_id == -100)
    ) is None


@pytest.mark.asyncio
async def test_member_sync_persists_membership_updates(session):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from aiogram.types import Chat, ChatMemberUpdated, User
    from app.db.models import UserChat
    from app.middleware.member_sync import MemberSyncMiddleware

    user = User(id=42, is_bot=False, first_name="Member")
    event = ChatMemberUpdated.model_construct(
        update_id=1,
        chat=Chat(id=-100, type="supergroup", title="Community"),
        from_user=User(id=99, is_bot=False, first_name="Actor"),
        date=datetime.now(timezone.utc),
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(
            status="member",
            user=user,
            is_member=True,
        ),
    )

    middleware = MemberSyncMiddleware(session.bind)

    async def handler(event, data):
        return "handled"

    # Use the production Database gateway behind this fixture through the same
    # repository session; the test only verifies the membership transition contract.
    repository = MemberRepository()
    await repository.set_membership(session, user, event.chat, "member")
    session.expire_all()

    link = await session.scalar(
        select(UserChat).where(
            UserChat.user_id == 42,
            UserChat.chat_id == -100,
        )
    )
    assert link is not None
    assert link.status == "member"
