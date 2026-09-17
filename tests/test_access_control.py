from datetime import datetime, timezone

import pytest
from aiogram.types import Chat, Message, Update, User

from app.core.config import Settings
from app.middleware.access_control import ChatAccessMiddleware


def make_update(*, chat_id: int, chat_type: str, user_id: int = 77) -> Update:
    message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=chat_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        text="/start",
    )
    return Update(update_id=1, message=message)


@pytest.mark.asyncio
async def test_authorized_group_reaches_handler() -> None:
    settings = Settings(authorized_chat_ids="-100123,-100456")
    middleware = ChatAccessMiddleware(settings)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "handled"

    update = make_update(chat_id=-100123, chat_type="supergroup")
    result = await middleware(handler, update, {"event_update": update})

    assert result == "handled"
    assert called is True


@pytest.mark.asyncio
async def test_unauthorized_group_is_blocked_before_handler() -> None:
    settings = Settings(authorized_chat_ids="-100123")
    middleware = ChatAccessMiddleware(settings)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "must-not-run"

    update = make_update(chat_id=-100999, chat_type="group")
    result = await middleware(handler, update, {"event_update": update})

    assert result is None
    assert called is False


@pytest.mark.asyncio
async def test_private_chat_is_limited_to_configured_admin() -> None:
    settings = Settings(admin_user_id=77, allow_admin_private_chat=True)
    middleware = ChatAccessMiddleware(settings)

    async def handler(event, data):
        return "handled"

    allowed = make_update(chat_id=77, chat_type="private", user_id=77)
    denied = make_update(chat_id=88, chat_type="private", user_id=88)

    assert await middleware(handler, allowed, {"event_update": allowed}) == "handled"
    assert await middleware(handler, denied, {"event_update": denied}) is None


def test_empty_or_malformed_allowlist_fails_closed() -> None:
    settings = Settings(authorized_chat_ids=" ,not-a-chat-id, ")
    middleware = ChatAccessMiddleware(settings)

    assert settings.authorized_chat_ids_set == frozenset()
    assert middleware._is_allowed(make_update(chat_id=-100123, chat_type="supergroup")) is False
