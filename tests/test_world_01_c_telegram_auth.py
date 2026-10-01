# -*- coding: utf-8 -*-
"""Targeted WORLD-01-C Telegram auth/context security tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.dependencies import authorize_cafe_access, get_current_user
from api.security.telegram_auth import (
    AuthenticatedTelegramActor,
    TelegramAuthError,
    extract_tma_init_data,
    validate_telegram_init_data,
)
from api.security.telegram_membership import (
    TelegramMembershipDecision,
    TelegramMembershipUnavailable,
    TelegramMembershipVerifier,
)
from api.security.trusted_context import (
    TrustedContextConfigurationError,
    TrustedContextError,
    TrustedContextRegistry,
    build_main_mini_app_link,
)


BOT_TOKEN = "123456:W01C_TEST_TOKEN"
CONTEXT_SECRET = "local-test-context-secret-0123456789"
AUTH_NOW = int(time.time())
USER = {
    "id": 123456789,
    "first_name": "Test",
    "last_name": "Nakama",
    "username": "nakama",
}


def sign_pairs(
    pairs: list[tuple[str, str]],
    bot_token: str = BOT_TOKEN,
) -> str:
    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(pairs)
    )
    secret = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return hmac.new(
        secret,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def make_init_data(
    *,
    user: dict | None = USER,
    auth_date: int = AUTH_NOW,
    bot_token: str = BOT_TOKEN,
    start_param: str = "tctx_TEST",
    extra: list[tuple[str, str]] | None = None,
) -> str:
    pairs: list[tuple[str, str]] = [
        ("auth_date", str(auth_date)),
    ]
    if user is not None:
        pairs.append(
            (
                "user",
                json.dumps(user, separators=(",", ":")),
            )
        )
    pairs.extend(
        [
            ("chat_instance", "123456789"),
            ("chat_type", "supergroup"),
            ("start_param", start_param),
        ]
    )
    if extra:
        pairs.extend(extra)
    digest = sign_pairs(pairs, bot_token)
    pairs.append(("hash", digest))
    return "&".join(
        f"{quote(key, safe='')}={quote(value, safe='')}"
        for key, value in pairs
    )


def async_run(coro):
    return asyncio.run(coro)


def test_valid_init_data_derives_server_actor() -> None:
    actor = validate_telegram_init_data(
        make_init_data(),
        BOT_TOKEN,
        now=AUTH_NOW,
    )
    assert actor.telegram_user_id == USER["id"]
    assert actor.id == USER["id"]
    assert actor.actor_key == "telegram:123456789"
    assert actor.start_param == "tctx_TEST"
    assert actor.chat_instance == "123456789"


def test_url_decoding_is_verified_before_actor_derivation() -> None:
    actor = validate_telegram_init_data(
        make_init_data(
            user={
                "id": USER["id"],
                "first_name": "A&B",
                "username": "quoted name",
            },
            start_param="tctx_A+B",
        ),
        BOT_TOKEN,
        now=AUTH_NOW,
    )
    assert actor.first_name == "A&B"
    assert actor.username == "quoted name"
    assert actor.start_param == "tctx_A+B"


def test_missing_hash_is_rejected() -> None:
    raw = make_init_data().rsplit("&hash=", 1)[0]
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(raw, BOT_TOKEN, now=AUTH_NOW)


def test_invalid_hash_is_rejected() -> None:
    raw = make_init_data()
    raw = raw[:-64] + ("0" * 64)
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(raw, BOT_TOKEN, now=AUTH_NOW)


def test_duplicate_fields_are_rejected() -> None:
    raw = make_init_data() + "&auth_date=" + str(AUTH_NOW)
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(raw, BOT_TOKEN, now=AUTH_NOW)


def test_malformed_query_field_is_rejected() -> None:
    raw = make_init_data() + "&broken"
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(raw, BOT_TOKEN, now=AUTH_NOW)


def test_missing_user_is_rejected() -> None:
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(
            make_init_data(user=None),
            BOT_TOKEN,
            now=AUTH_NOW,
        )


def test_invalid_user_json_is_rejected() -> None:
    pairs = [
        ("auth_date", str(AUTH_NOW)),
        ("user", "not-json"),
        ("chat_instance", "123456789"),
        ("chat_type", "supergroup"),
        ("start_param", "tctx_TEST"),
    ]
    raw = "&".join(
        f"{key}={value}"
        for key, value in pairs + [("hash", sign_pairs(pairs))]
    )
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(raw, BOT_TOKEN, now=AUTH_NOW)


def test_invalid_user_id_is_rejected() -> None:
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(
            make_init_data(user={"id": 0}),
            BOT_TOKEN,
            now=AUTH_NOW,
        )


def test_future_and_expired_auth_date_are_rejected() -> None:
    expired = make_init_data(auth_date=AUTH_NOW - 3601)
    future = make_init_data(auth_date=AUTH_NOW + 31)
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(expired, BOT_TOKEN, now=AUTH_NOW)
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(future, BOT_TOKEN, now=AUTH_NOW)


def test_wrong_bot_token_is_rejected() -> None:
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(
            make_init_data(),
            "123456:WRONG",
            now=AUTH_NOW,
        )


def test_unexpected_fields_remain_integrity_protected() -> None:
    actor = validate_telegram_init_data(
        make_init_data(extra=[("future_field", "signed-value")]),
        BOT_TOKEN,
        now=AUTH_NOW,
    )
    assert actor.telegram_user_id == USER["id"]


def test_init_data_unsafe_never_grants_identity() -> None:
    actor = validate_telegram_init_data(
        make_init_data(),
        BOT_TOKEN,
        now=AUTH_NOW,
    )
    unsafe_only = {"id": 999999999, "username": "attacker"}
    assert actor.telegram_user_id != unsafe_only["id"]


def test_auth_header_accepts_only_tma_scheme() -> None:
    init_data = make_init_data()
    assert extract_tma_init_data("tma " + init_data) == init_data
    with pytest.raises(TelegramAuthError):
        extract_tma_init_data("Bearer " + init_data)
    with pytest.raises(TelegramAuthError):
        extract_tma_init_data("tma")
    with pytest.raises(TelegramAuthError):
        extract_tma_init_data(None)


def test_auth_exceptions_do_not_contain_secret_material() -> None:
    raw = make_init_data()
    with pytest.raises(TelegramAuthError) as captured:
        validate_telegram_init_data(
            raw[:-1] + "0",
            BOT_TOKEN,
            now=AUTH_NOW,
        )
    assert BOT_TOKEN not in str(captured.value)
    assert raw not in str(captured.value)


class FakeRoute:
    def __init__(
        self,
        chat_id: str,
        message_thread_id: int,
        room_key: str,
    ) -> None:
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.room_key = room_key


class FakeRouter:
    def __init__(
        self,
        routes: tuple[FakeRoute, ...],
    ) -> None:
        self.routes = routes

    def resolve(
        self,
        chat_id: str,
        message_thread_id: int,
    ) -> str | None:
        for route in self.routes:
            if (
                route.chat_id == str(chat_id)
                and route.message_thread_id == int(message_thread_id)
            ):
                return route.room_key
        return None

    def list_routes(self) -> tuple[FakeRoute, ...]:
        return self.routes


def test_trusted_context_is_opaque_reusable_and_room_bound() -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, CONTEXT_SECRET)
    context = registry.issue("-100", 42)
    resolved = registry.resolve(context.reference)

    assert context.reference.startswith("tctx_")
    assert len(context.reference) == 48
    assert context.room_key == "general"
    assert "-100" not in context.reference
    assert "42" not in context.reference
    assert "general" not in context.reference
    assert resolved == context
    assert registry.issue("-100", 42).reference == context.reference


def test_context_requires_long_secret() -> None:
    with pytest.raises(TrustedContextConfigurationError):
        TrustedContextRegistry(
            FakeRouter((FakeRoute("-100", 42, "general"),)),
            "too-short",
        )


def test_unknown_context_reference_is_rejected() -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        CONTEXT_SECRET,
    )
    with pytest.raises(TrustedContextError):
        registry.resolve("tctx_" + "A" * 43)


def test_route_removal_invalidates_context() -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, CONTEXT_SECRET)
    reference = registry.issue("-100", 42).reference
    router.routes = ()
    with pytest.raises(TrustedContextError):
        registry.resolve(reference)


def test_context_from_foreign_room_is_not_remapped() -> None:
    router = FakeRouter(
        (
            FakeRoute("-100", 42, "general"),
            FakeRoute("-100", 99, "tcg_collection"),
        )
    )
    registry = TrustedContextRegistry(router, CONTEXT_SECRET)
    foreign = registry.issue("-100", 99)
    resolved = registry.resolve(foreign.reference)

    assert resolved.room_key == "tcg_collection"
    assert resolved.message_thread_id == 99
    assert resolved.reference == foreign.reference


def test_context_launcher_uses_main_startapp() -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        CONTEXT_SECRET,
    )
    reference = registry.issue("-100", 42).reference
    link = build_main_mini_app_link(
        "CafeOtakuBot",
        reference,
    )
    assert link.startswith(
        "https://t.me/CafeOtakuBot?startapp=tctx_"
    )


def test_semantic_room_reference_is_rejected() -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        CONTEXT_SECRET,
    )
    with pytest.raises(TrustedContextError):
        registry.resolve("general")


class FakeMember:
    def __init__(
        self,
        status: str,
        *,
        user_id: int = USER["id"],
        is_member: bool | None = None,
    ) -> None:
        self.status = status
        self.user = SimpleNamespace(id=user_id)
        if is_member is not None:
            self.is_member = is_member


class FakeBot:
    def __init__(
        self,
        member=None,
        error: Exception | None = None,
    ) -> None:
        self.member = member
        self.error = error
        self.requested = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get_chat_member(
        self,
        chat_id,
        user_id,
    ):
        self.requested = (chat_id, user_id)
        if self.error:
            raise self.error
        return self.member


@pytest.mark.parametrize(
    "status",
    [
        "creator",
        "administrator",
        "member",
    ],
)
def test_membership_allows_active_members(status: str) -> None:
    bot = FakeBot(FakeMember(status))
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: bot,
    )
    decision = async_run(verifier.check("-100", USER["id"]))
    assert decision.allowed is True
    assert decision.status == status
    assert bot.requested == (-100, USER["id"])


def test_restricted_requires_is_member_true() -> None:
    allowed = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(
            FakeMember("restricted", is_member=True)
        ),
    )
    denied = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(
            FakeMember("restricted", is_member=False)
        ),
    )
    assert async_run(allowed.check("-100", USER["id"])).allowed is True
    assert async_run(denied.check("-100", USER["id"])).allowed is False


@pytest.mark.parametrize(
    "status",
    [
        "left",
        "kicked",
        "banned",
        "unknown",
    ],
)
def test_membership_denies_nonmember_states(status: str) -> None:
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(FakeMember(status)),
    )
    assert async_run(verifier.check("-100", USER["id"])).allowed is False


def test_membership_rejects_returned_identity_mismatch() -> None:
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(
            FakeMember("member", user_id=999)
        ),
    )
    decision = async_run(verifier.check("-100", USER["id"]))
    assert decision.allowed is False


def test_membership_api_failure_fails_closed() -> None:
    class FakeTelegramError(Exception):
        __module__ = "telegram.error"

    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(
            error=FakeTelegramError("network")
        ),
    )
    with pytest.raises(TelegramMembershipUnavailable):
        async_run(verifier.check("-100", USER["id"]))


def test_membership_timeout_fails_closed() -> None:
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(
            error=TimeoutError()
        ),
    )
    with pytest.raises(TelegramMembershipUnavailable):
        async_run(verifier.check("-100", USER["id"]))


def test_fastapi_missing_bot_token_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    app = FastAPI()

    @app.get("/actor")
    async def actor(current=Depends(get_current_user)):
        return current.model_dump()

    response = TestClient(app).get("/actor")
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Telegram authentication dependency is not configured"
    )


def test_fastapi_rejects_non_tma_scheme(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    app = FastAPI()

    @app.get("/actor")
    async def actor(current=Depends(get_current_user)):
        return current.model_dump()

    response = TestClient(app).get(
        "/actor",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401
    assert BOT_TOKEN not in response.text


def test_fastapi_authenticated_actor_is_server_derived(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    app = FastAPI()

    @app.get("/actor")
    async def actor(current=Depends(get_current_user)):
        return {
            "telegram_user_id": current.telegram_user_id,
            "actor_key": current.actor_key,
        }

    response = TestClient(app).get(
        "/actor",
        headers={"Authorization": "tma " + make_init_data()},
    )
    assert response.status_code == 200
    assert response.json() == {
        "telegram_user_id": USER["id"],
        "actor_key": "telegram:123456789",
    }


def test_full_pipeline_allows_authorized_member() -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, CONTEXT_SECRET)
    reference = registry.issue("-100", 42).reference
    actor = validate_telegram_init_data(
        make_init_data(start_param=reference),
        BOT_TOKEN,
        now=AUTH_NOW,
    )

    class AllowingVerifier:
        async def check(self, chat_id: str, user_id: int):
            assert chat_id == "-100"
            assert user_id == USER["id"]
            return TelegramMembershipDecision(
                status="member",
                allowed=True,
            )

    access = async_run(
        authorize_cafe_access(
            actor,
            actor.start_param,
            registry,
            AllowingVerifier(),
        )
    )
    assert access.actor.actor_key == "telegram:123456789"
    assert access.context.room_key == "general"
    assert access.context.message_thread_id == 42


def test_full_pipeline_denies_membership() -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, CONTEXT_SECRET)
    reference = registry.issue("-100", 42).reference
    actor = validate_telegram_init_data(
        make_init_data(start_param=reference),
        BOT_TOKEN,
        now=AUTH_NOW,
    )

    class DenyingVerifier:
        async def check(self, chat_id: str, user_id: int):
            return TelegramMembershipDecision(
                status="member",
                allowed=False,
            )

    with pytest.raises(Exception) as captured:
        async_run(
            authorize_cafe_access(
                actor,
                actor.start_param,
                registry,
                DenyingVerifier(),
            )
        )
    assert getattr(captured.value, "status_code", None) == 403


def test_full_pipeline_unknown_context_denies() -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, CONTEXT_SECRET)
    actor = validate_telegram_init_data(
        make_init_data(),
        BOT_TOKEN,
        now=AUTH_NOW,
    )

    with pytest.raises(Exception) as captured:
        async_run(
            authorize_cafe_access(
                actor,
                "tctx_" + "A" * 43,
                registry,
                TelegramMembershipVerifier(
                    BOT_TOKEN,
                    bot_factory=lambda _: FakeBot(
                        FakeMember("member")
                    ),
                ),
            )
        )
    assert getattr(captured.value, "status_code", None) == 404


def test_context_secret_is_not_exposed_in_configuration_error() -> None:
    with pytest.raises(TrustedContextConfigurationError) as captured:
        TrustedContextRegistry(
            FakeRouter((FakeRoute("-100", 42, "general"),)),
            CONTEXT_SECRET[:4],
        )
    assert CONTEXT_SECRET not in str(captured.value)


def test_actor_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        AuthenticatedTelegramActor(
            telegram_user_id=1,
            actor_key="telegram:1",
            auth_date=AUTH_NOW,
            unexpected="client-authority",
        )
