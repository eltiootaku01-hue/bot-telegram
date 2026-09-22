from datetime import datetime, timezone

import pytest
from aiogram.types import CallbackQuery, Chat, Message, PreCheckoutQuery, Update, User

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.core.social_runtime import SocialRuntime
from app.middleware.access_control import ChatAccessMiddleware


def make_update(*, chat_id: int, chat_type: str, user_id: int = 77, text: str = "/start") -> Update:
    message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=chat_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        text=text,
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
async def test_private_user_features_are_available_to_normal_users_by_default() -> None:
    settings = Settings(admin_user_id=77, allow_user_private_chat=True)
    middleware = ChatAccessMiddleware(settings)

    async def handler(event, data):
        return "handled"

    update = make_update(chat_id=88, chat_type="private", user_id=88)

    assert await middleware(handler, update, {"event_update": update}) == "handled"


@pytest.mark.asyncio
async def test_private_access_can_be_restricted_to_admin_when_requested() -> None:
    settings = Settings(
        admin_user_id=77,
        allow_admin_private_chat=True,
        allow_user_private_chat=False,
    )
    middleware = ChatAccessMiddleware(settings)

    async def handler(event, data):
        return "handled"

    allowed = make_update(chat_id=77, chat_type="private", user_id=77)
    denied = make_update(chat_id=88, chat_type="private", user_id=88)

    assert await middleware(handler, allowed, {"event_update": allowed}) == "handled"
    assert await middleware(handler, denied, {"event_update": denied}) is None


@pytest.mark.asyncio
async def test_private_access_can_be_disabled_for_everyone() -> None:
    settings = Settings(
        admin_user_id=77,
        allow_admin_private_chat=False,
        allow_user_private_chat=False,
    )
    middleware = ChatAccessMiddleware(settings)

    async def handler(event, data):
        return "must-not-run"

    update = make_update(chat_id=77, chat_type="private", user_id=77)

    assert await middleware(handler, update, {"event_update": update}) is None


def test_empty_or_malformed_allowlist_fails_closed() -> None:
    settings = Settings(authorized_chat_ids=" ,not-a-chat-id, ")
    middleware = ChatAccessMiddleware(settings)

    assert settings.authorized_chat_ids_set == frozenset()
    assert middleware._is_allowed(make_update(chat_id=-100123, chat_type="supergroup")) is False


def test_malformed_allowlist_entries_do_not_expand_access() -> None:
    settings = Settings(authorized_chat_ids="-100123,  ,abc, -100456xyz, -100456")

    assert settings.authorized_chat_ids_set == frozenset({-100123, -100456})
    assert settings.is_chat_allowed(-100999, "group") is False


def test_central_chat_policy_matches_middleware_rules() -> None:
    settings = Settings(authorized_chat_ids="-100123", admin_user_id=77)

    assert settings.is_chat_allowed(-100123, "group") is True
    assert settings.is_chat_allowed(-100999, "supergroup") is False
    assert settings.is_chat_allowed(77, "private", 77) is True
    assert settings.is_chat_allowed(88, "private", 88) is True
    assert settings.is_chat_allowed(-100123, "channel") is False


@pytest.mark.asyncio
async def test_social_runtime_skips_unauthorized_chat_before_database_work() -> None:
    settings = Settings(authorized_chat_ids="-100123")
    runtime = SocialRuntime(database=None, identity=BotIdentity.CARI, settings=settings)

    result = await runtime._tick_chat(bot=None, chat_id=-100999, now=datetime.now(timezone.utc))

    assert result is False



@pytest.mark.asyncio
async def test_private_callback_uses_clicking_user_not_message_author() -> None:
    settings = Settings(admin_user_id=77, allow_admin_private_chat=True)
    middleware = ChatAccessMiddleware(settings)

    async def handler(event, data):
        return "handled"

    message = Message(
        message_id=2,
        date=datetime.now(timezone.utc),
        chat=Chat(id=77, type="private"),
        from_user=User(id=999, is_bot=True, first_name="Sunna"),
    )
    callback = CallbackQuery(
        id="callback-1",
        from_user=User(id=77, is_bot=False, first_name="Admin"),
        chat_instance="chat-instance",
        message=message,
    )
    update = Update(update_id=2, callback_query=callback)

    assert await middleware(handler, update, {"event_update": update}) == "handled"


def test_authorized_community_requires_allowlisted_group_or_supergroup() -> None:
    from app.core.access import is_authorized_community

    settings = Settings(authorized_chat_ids="-100123")
    assert is_authorized_community(settings, -100123) is True
    assert is_authorized_community(settings, -100999) is False


def test_authorized_membership_update_reaches_access_policy() -> None:
    from types import SimpleNamespace

    settings = Settings(authorized_chat_ids="-100123")
    middleware = ChatAccessMiddleware(settings)

    update = Update.model_construct(
        update_id=90,
        chat_member=SimpleNamespace(
            chat=Chat(id=-100123, type="supergroup"),
        ),
    )
    denied = Update.model_construct(
        update_id=91,
        chat_member=SimpleNamespace(
            chat=Chat(id=-100999, type="supergroup"),
        ),
    )

    assert middleware._is_allowed(update) is True
    assert middleware._is_allowed(denied) is False


@pytest.mark.asyncio
async def test_unauthorized_group_allows_admin_chie_bootstrap_command() -> None:
    settings = Settings(authorized_chat_ids="")
    middleware = ChatAccessMiddleware(settings)

    class BotStub:
        async def get_chat_member(self, chat_id, user_id):
            return type("MemberStub", (), {"status": "administrator"})()

    async def handler(event, data):
        return data.get(ChatAccessMiddleware.BOOTSTRAP_FLAG, False)

    message = make_update(
        chat_id=-100999,
        chat_type="supergroup",
        user_id=77,
        text="/configurar",
    ).message
    update = Update(update_id=100, message=message)

    result = await middleware(
        handler,
        update,
        {"event_update": update, "bot": BotStub()},
    )
    assert result is True


@pytest.mark.asyncio
async def test_unauthorized_group_bootstrap_rejects_non_admin() -> None:
    settings = Settings(authorized_chat_ids="")
    middleware = ChatAccessMiddleware(settings)

    class BotStub:
        async def get_chat_member(self, chat_id, user_id):
            return object()

    async def handler(event, data):
        return "must-not-run"

    message = make_update(
        chat_id=-100999,
        chat_type="supergroup",
        user_id=77,
        text="/configurar",
    ).message
    update = Update(update_id=101, message=message)

    assert await middleware(
        handler,
        update,
        {"event_update": update, "bot": BotStub()},
    ) is None


def test_authorized_media_channel_post_reaches_access_policy() -> None:
    from aiogram.types import PhotoSize

    settings = Settings(media_storage_chat_id=-100555)
    middleware = ChatAccessMiddleware(settings)
    channel_post = Message(
        message_id=12,
        date=datetime.now(timezone.utc),
        chat=Chat(id=-100555, type="channel"),
        photo=[
            PhotoSize(
                file_id="file",
                file_unique_id="unique",
                width=1,
                height=1,
            )
        ],
    )
    update = Update(update_id=120, channel_post=channel_post)

    assert middleware._is_allowed(update) is True


def test_unauthorized_media_channel_post_is_blocked() -> None:
    settings = Settings(media_storage_chat_id=-100555)
    middleware = ChatAccessMiddleware(settings)
    channel_post = Message(
        message_id=13,
        date=datetime.now(timezone.utc),
        chat=Chat(id=-100777, type="channel"),
    )
    update = Update(update_id=121, channel_post=channel_post)

    assert middleware._is_allowed(update) is False


@pytest.mark.asyncio
async def test_pre_checkout_query_reaches_payment_handler_without_message() -> None:
    settings = Settings(
        admin_user_id=77,
        allow_admin_private_chat=True,
        allow_user_private_chat=False,
    )
    middleware = ChatAccessMiddleware(settings)

    async def handler(event, data):
        return "payment-handler"

    query = PreCheckoutQuery(
        id="checkout-1",
        from_user=User(id=77, is_bot=False, first_name="Admin"),
        currency="XTR",
        total_amount=10,
        invoice_payload="tma:77:premium_ticket:0123456789abcdef0123456789abcdef",
    )
    update = Update(update_id=140, pre_checkout_query=query)

    assert await middleware(handler, update, {"event_update": update}) == "payment-handler"
