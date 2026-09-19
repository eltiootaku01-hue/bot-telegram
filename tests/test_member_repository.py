from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from aiogram.types import Chat as TgChat, ChatMemberUpdated, User as TgUser
from sqlalchemy import select

from app.db.database import Database
from app.db.models import Chat, User, UserChat
from app.db.repositories import MemberRepository
from app.middleware.member_sync import MemberSyncMiddleware


@pytest.fixture
async def session():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as db:
        yield db
    await database.close()


@pytest.fixture
async def database():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    yield database
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


def membership_update(*, status: str, old_status: str = "left", is_member: bool | None = None) -> ChatMemberUpdated:
    user = TgUser(id=42, is_bot=False, first_name="Member")
    return ChatMemberUpdated.model_construct(
        update_id=1,
        chat=TgChat(id=-100123, type="supergroup", title="Community"),
        from_user=TgUser(id=99, is_bot=False, first_name="Actor"),
        date=datetime.now(timezone.utc),
        old_chat_member=SimpleNamespace(status=old_status),
        new_chat_member=SimpleNamespace(
            status=status,
            user=user,
            is_member=is_member,
        ),
    )


@pytest.mark.asyncio
async def test_member_sync_persists_join_and_leave(database: Database) -> None:
    middleware = MemberSyncMiddleware(database)

    async def handler(event, data):
        return "handled"

    assert await middleware(handler, membership_update(status="member"), {}) == "handled"

    async with database.session() as session:
        joined = await session.scalar(
            select(UserChat).where(
                UserChat.user_id == 42,
                UserChat.chat_id == -100123,
            )
        )

    assert joined is not None
    assert joined.status == "member"
    assert joined.message_count == 0
    assert joined.joined_at is not None
    assert joined.left_at is None

    event = membership_update(status="left", old_status="member")
    assert await middleware(handler, event, {}) == "handled"

    async with database.session() as session:
        left = await session.scalar(
            select(UserChat).where(
                UserChat.user_id == 42,
                UserChat.chat_id == -100123,
            )
        )

    assert left is not None
    assert left.status == "left"
    assert left.message_count == 0
    assert left.left_at is not None


@pytest.mark.asyncio
async def test_member_sync_maps_restricted_membership(database: Database) -> None:
    middleware = MemberSyncMiddleware(database)

    async def handler(event, data):
        return None

    await middleware(handler, membership_update(status="restricted", is_member=True), {})

    async with database.session() as session:
        link = await session.scalar(
            select(UserChat).where(
                UserChat.user_id == 42,
                UserChat.chat_id == -100123,
            )
        )

    assert link is not None
    assert link.status == "member"
