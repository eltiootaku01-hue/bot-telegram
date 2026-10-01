# -*- coding: utf-8 -*-
"""Targeted WORLD-01-C Telegram auth/context security tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from pathlib import Path
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
AUTH_NOW = 1_800_000_000
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
    start_param: str = "tctx_placeholder",
    extra: list[tuple[str, str]] | None = None,
) -> str:
    pairs: list[tuple[str, str]] = [("auth_date", str(auth_date))]
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
    assert actor.start_param == "tctx_placeholder"


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
        ("start_param", "tctx_placeholder"),
    ]
    raw = "&".join(
        f"{key}={value}"
        for key, value in pairs + [("hash", sign_pairs(pairs))]
    )
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(raw, BOT_TOKEN, now=AUTH_NOW)


@pytest.mark.parametrize(
    "auth_date",
    [AUTH_NOW - 3601, AUTH_NOW + 31],
)
def test_auth_date_freshness_and_future_tolerance(auth_date: int) -> None:
    with pytest.raises(TelegramAuthError):
        validate_telegram_init_data(
            make_init_data(auth_date=auth_date),
            BOT_TOKEN,
            now=AUTH_NOW,
        )


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


def test_auth_header_accepts_only_tma_scheme() -> None:
    init_data = make_init_data()
    assert extract_tma_init_data("tma " + init_data) == init_data
    for value in (None, "Bearer " + init_data, "tma"):
        with pytest.raises(TelegramAuthError):
            extract_tma_init_data(value)


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
    def __init__(self, routes: tuple[FakeRoute, ...]) -> None:
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


def test_context_is_random_opaque_reusable_and_room_bound(
    tmp_path: Path,
) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(
        router,
        store_dir=tmp_path / "contexts",
        max_age_seconds=3600,
        issuer="cafe-otaku",
    )
    first = registry.issue("-100", 42, now=AUTH_NOW)
    second = registry.issue("-100", 42, now=AUTH_NOW)

    assert first.reference.startswith("tctx_")
    assert len(first.reference) == 48
    assert first.reference != second.reference
    assert "-100" not in first.reference
    assert "42" not in first.reference
    assert "general" not in first.reference
    assert registry.resolve(first.reference, now=AUTH_NOW) == first
    assert registry.resolve(first.reference, now=AUTH_NOW + 3599) == first
    assert len(list((tmp_path / "contexts").glob("*.json"))) == 2


def test_context_expiry_denies_reference(tmp_path: Path) -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
        max_age_seconds=60,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    with pytest.raises(TrustedContextError):
        registry.resolve(reference, now=AUTH_NOW + 60)


def test_context_revocation_denies_reference(tmp_path: Path) -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    revoked = registry.revoke(reference, now=AUTH_NOW + 1)
    assert revoked.revoked_at == AUTH_NOW + 1
    with pytest.raises(TrustedContextError):
        registry.resolve(reference, now=AUTH_NOW + 2)


def test_route_removal_invalidates_context(tmp_path: Path) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path)
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    router.routes = ()
    with pytest.raises(TrustedContextError):
        registry.resolve(reference, now=AUTH_NOW)


def test_route_remap_invalidates_context(tmp_path: Path) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path)
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    router.routes = (FakeRoute("-100", 42, "tcg_collection"),)
    with pytest.raises(TrustedContextError):
        registry.resolve(reference, now=AUTH_NOW)


def test_context_requires_valid_configuration(tmp_path: Path) -> None:
    with pytest.raises(TrustedContextConfigurationError):
        TrustedContextRegistry(
            FakeRouter((FakeRoute("-100", 42, "general"),)),
            store_dir=tmp_path,
            max_age_seconds=0,
        )


def test_unknown_and_semantic_contexts_are_rejected(tmp_path: Path) -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
    )
    for reference in ("general", "tctx_" + "A" * 43):
        with pytest.raises(TrustedContextError):
            registry.resolve(reference, now=AUTH_NOW)


def test_context_launcher_uses_main_startapp(tmp_path: Path) -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    link = build_main_mini_app_link("CafeOtakuBot", reference)
    assert link.startswith("https://t.me/CafeOtakuBot?startapp=tctx_")


def test_real_room_router_is_authoritative(tmp_path: Path) -> None:
    from bot_ia.interfaces.telegram_room_routing import TelegramRoomRouter

    router = TelegramRoomRouter(tmp_path / "telegram_rooms.sqlite3")

    class Room:
        name = "#general"
        key = "general"
        external_id = "42"

    router.replace_chat_rooms("-100", (Room(),))
    assert router.resolve("-100", 42) == "general"


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

    async def get_chat_member(self, chat_id, user_id):
        self.requested = (chat_id, user_id)
        if self.error:
            raise self.error
        return self.member


@pytest.mark.parametrize(
    "status",
    ["creator", "administrator", "member"],
)
def test_membership_allows_active_members(status: str) -> None:
    bot = FakeBot(FakeMember(status))
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: bot,
    )
    decision = async_run(verifier.check("-100", USER["id"]))
    assert decision.allowed is True
    assert bot.requested == (-100, USER["id"])


@pytest.mark.parametrize("is_member", [True, False])
def test_restricted_policy_follows_is_member_flag(is_member: bool) -> None:
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(
            FakeMember("restricted", is_member=is_member)
        ),
    )
    decision = async_run(verifier.check("-100", USER["id"]))
    assert decision.allowed is is_member


@pytest.mark.parametrize(
    "status",
    ["left", "kicked", "banned", "unknown"],
)
def test_membership_denies_nonmember_states(status: str) -> None:
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(FakeMember(status)),
    )
    assert async_run(
        verifier.check("-100", USER["id"])
    ).allowed is False


def test_membership_rejects_returned_identity_mismatch() -> None:
    verifier = TelegramMembershipVerifier(
        BOT_TOKEN,
        bot_factory=lambda _: FakeBot(
            FakeMember("member", user_id=999)
        ),
    )
    assert async_run(
        verifier.check("-100", USER["id"])
    ).allowed is False


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
        bot_factory=lambda _: FakeBot(error=TimeoutError())
    )
    with pytest.raises(TelegramMembershipUnavailable):
        async_run(verifier.check("-100", USER["id"]))


def test_fastapi_missing_bot_token_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    app = FastAPI()

    @app.get("/actor")
    async def actor(current=Depends(get_current_user)):
        return current.model_dump()

    response = TestClient(app).get(
        "/actor",
        headers={"Authorization": "tma " + make_init_data()},
    )
    assert response.status_code == 503
    assert BOT_TOKEN not in response.text


def test_fastapi_invalid_tma_configuration_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("TMA_AUTH_MAX_AGE_SECONDS", "0")
    app = FastAPI()

    @app.get("/actor")
    async def actor(current=Depends(get_current_user)):
        return current.model_dump()

    response = TestClient(app).get(
        "/actor",
        headers={"Authorization": "tma " + make_init_data()},
    )
    assert response.status_code == 503
    assert BOT_TOKEN not in response.text


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


def test_full_pipeline_allows_authorized_member(tmp_path: Path) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path)
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
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


def test_full_pipeline_denies_foreign_context(tmp_path: Path) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path)
    actor = validate_telegram_init_data(
        make_init_data(start_param="tctx_" + "A" * 43),
        BOT_TOKEN,
        now=AUTH_NOW,
    )
    with pytest.raises(Exception) as captured:
        async_run(
            authorize_cafe_access(
                actor,
                actor.start_param,
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


def test_full_pipeline_denies_unknown_room(tmp_path: Path) -> None:
    registry = TrustedContextRegistry(
        FakeRouter(()),
        store_dir=tmp_path,
    )
    with pytest.raises(TrustedContextError):
        registry.issue("-100", 42, now=AUTH_NOW)


def test_full_pipeline_denies_membership(tmp_path: Path) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path)
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
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


def test_actor_model_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        AuthenticatedTelegramActor(
            telegram_user_id=1,
            actor_key="telegram:1",
            auth_date=AUTH_NOW,
            unexpected="client-authority",
        )


def test_actor_model_rejects_mismatched_actor_key() -> None:
    with pytest.raises(ValidationError):
        AuthenticatedTelegramActor(
            telegram_user_id=1,
            actor_key="discord:1",
            auth_date=AUTH_NOW,
        )
