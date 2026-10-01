# -*- coding: utf-8 -*-
"""Targeted WORLD-01-C Telegram auth/context security tests."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import stat
import hmac
import json
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.dependencies import (
    authorize_cafe_access,
    get_current_cafe_access,
    get_current_user,
    get_trusted_context_registry,
)
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
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramOutbound
from bot_ia.interfaces.telegram_room_routing import (
    TelegramRoomRouter,
    TelegramRoomRoutingError,
)


BOT_TOKEN = "123456:W01C_TEST_TOKEN"
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


def test_context_store_uses_private_files_when_supported(
    tmp_path: Path,
) -> None:
    store_dir = tmp_path / "contexts"
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=store_dir,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    record_path = store_dir / f"{reference}.json"

    if os.name != "nt":
        assert stat.S_IMODE(store_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(record_path.stat().st_mode) == 0o600


def test_context_store_missing_is_not_created_for_read_only_registry(
    tmp_path: Path,
) -> None:
    store_dir = tmp_path / "missing-contexts"
    with pytest.raises(TrustedContextConfigurationError):
        TrustedContextRegistry(
            FakeRouter((FakeRoute("-100", 42, "general"),)),
            store_dir=store_dir,
            create_store_dir=False,
        )
    assert not store_dir.exists()


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


def test_concurrent_issue_handles_same_reference_collision(
    tmp_path: Path,
) -> None:
    shared_reference = "A" * 43
    fallback_references = iter(["B" * 43, "C" * 43])
    from threading import Lock

    calls = {"count": 0}
    lock = Lock()

    def collision_factory(_: int) -> str:
        with lock:
            calls["count"] += 1
            if calls["count"] <= 2:
                return shared_reference
            return next(fallback_references)

    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
        token_factory=collision_factory,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        references = list(
            pool.map(
                lambda _: registry.issue("-100", 42, now=AUTH_NOW).reference,
                range(2),
            )
        )

    assert len(set(references)) == 2



def test_concurrent_revoke_is_idempotent_and_fail_closed(
    tmp_path: Path,
) -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(
                registry.revoke,
                reference,
                now=AUTH_NOW + 1,
            )
            for _ in range(16)
        ]
        results = [future.result() for future in futures]

    assert all(result.revoked_at == AUTH_NOW + 1 for result in results)
    with pytest.raises(TrustedContextError) as captured:
        registry.resolve(reference, now=AUTH_NOW + 2)
    assert captured.value.args[0] == "revoked_context_reference"


def test_concurrent_revoke_across_independent_registries_is_shared_and_atomic(
    tmp_path: Path,
) -> None:
    from threading import Barrier

    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    store_dir = tmp_path / "contexts"
    registry_a = TrustedContextRegistry(router, store_dir=store_dir)
    registry_b = TrustedContextRegistry(router, store_dir=store_dir)

    assert registry_a._store_dir == registry_b._store_dir
    reference = registry_a.issue("-100", 42, now=AUTH_NOW).reference
    stored = registry_b._load(reference)
    assert stored.reference == reference
    assert stored.revoked_at is None

    from api.security import trusted_context as trusted_context_module

    assert (
        trusted_context_module._revocation_lock(reference)
        is trusted_context_module._revocation_lock(reference)
    )

    worker_count = 16
    start_barrier = Barrier(worker_count)
    registries = tuple(
        registry_a if index % 2 == 0 else registry_b
        for index in range(worker_count)
    )

    def revoke_once(index: int):
        start_barrier.wait()
        return registries[index].revoke(
            reference,
            now=AUTH_NOW + 1,
        )

    errors = []
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(revoke_once, index) for index in range(worker_count)]
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except Exception as error:
                errors.append(error)

    assert not any(
        isinstance(error, TrustedContextError)
        and str(error) == "context_store_unavailable"
        for error in errors
    )
    assert not any(
        isinstance(error, PermissionError)
        and (
            getattr(error, "winerror", None) == 5
            or "WinError 5" in str(error)
        )
        for error in errors
    )
    assert not errors
    assert len(results) == worker_count
    assert {result.revoked_at for result in results} == {AUTH_NOW + 1}

    record_path = store_dir / f"{reference}.json"
    raw = record_path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["reference"] == reference
    assert payload["revoked_at"] == AUTH_NOW + 1
    assert len(list(store_dir.glob("*.json"))) == 1
    assert list(store_dir.glob("*.tmp")) == []
    assert list(store_dir.glob(f".{reference}.*.tmp")) == []

    with pytest.raises(TrustedContextError) as captured:
        registry_a.resolve(reference, now=AUTH_NOW + 2)
    assert captured.value.args[0] == "revoked_context_reference"


def test_concurrent_revoke_and_resolve_preserve_valid_records(
    tmp_path: Path,
) -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference

    def resolve_once(_: int) -> str:
        try:
            registry.resolve(reference, now=AUTH_NOW)
            return "allowed"
        except TrustedContextError as error:
            return error.args[0] if error.args else ""

    with ThreadPoolExecutor(max_workers=8) as pool:
        resolve_futures = [pool.submit(resolve_once, index) for index in range(32)]
        revoke_future = pool.submit(
            registry.revoke,
            reference,
            now=AUTH_NOW + 1,
        )
        outcomes = [future.result() for future in resolve_futures]
        revoke_future.result()

    assert all(
        outcome in {"allowed", "revoked_context_reference"}
        for outcome in outcomes
    )
    with pytest.raises(TrustedContextError) as captured:
        registry.resolve(reference, now=AUTH_NOW + 2)
    assert captured.value.args[0] == "revoked_context_reference"


def test_context_launcher_uses_main_startapp(tmp_path: Path) -> None:
    registry = TrustedContextRegistry(
        FakeRouter((FakeRoute("-100", 42, "general"),)),
        store_dir=tmp_path,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    link = build_main_mini_app_link("CafeOtakuBot", reference)
    assert link.startswith("https://t.me/CafeOtakuBot?startapp=tctx_")


def test_read_only_room_router_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "missing" / "telegram_rooms.sqlite3"
    with pytest.raises(TelegramRoomRoutingError):
        TelegramRoomRouter(database_path, read_only=True)
    assert not database_path.exists()
    assert not database_path.parent.exists()


def test_read_only_room_router_resolves_existing_route(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "telegram_rooms.sqlite3"
    writable = TelegramRoomRouter(database_path)

    class Room:
        name = "#general"
        key = "general"
        external_id = "42"

    writable.replace_chat_rooms("-100", (Room(),))
    read_only = TelegramRoomRouter(database_path, read_only=True)
    assert read_only.resolve("-100", 42) == "general"


def test_fastapi_room_registry_is_read_only_when_routing_database_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.dependencies as dependencies

    monkeypatch.setattr(dependencies, "PROJECT_ROOT", tmp_path)
    with pytest.raises(HTTPException) as captured:
        get_trusted_context_registry()
    assert captured.value.status_code == 503
    routing_path = tmp_path / "config" / "telegram_rooms.sqlite3"
    assert not routing_path.exists()
    assert not routing_path.parent.exists()



def test_context_store_unavailable_maps_to_503() -> None:
    class BrokenRegistry:
        def resolve(self, reference: str):
            raise TrustedContextError("context_store_unavailable")

    class NeverCalledVerifier:
        async def check(self, chat_id: str, user_id: int):
            raise AssertionError("membership must not run when storage is unavailable")

    actor = validate_telegram_init_data(
        make_init_data(start_param="tctx_" + "A" * 43),
        BOT_TOKEN,
        now=AUTH_NOW,
    )
    with pytest.raises(HTTPException) as captured:
        async_run(
            authorize_cafe_access(
                actor,
                actor.start_param,
                BrokenRegistry(),
                NeverCalledVerifier(),
            )
        )
    assert captured.value.status_code == 503


def test_fastapi_context_store_missing_maps_to_503(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.dependencies as dependencies

    routing_path = tmp_path / "config" / "telegram_rooms.sqlite3"
    routing_path.parent.mkdir(parents=True)
    router = TelegramRoomRouter(routing_path)

    class Room:
        name = "#general"
        key = "general"
        external_id = "42"

    router.replace_chat_rooms("-100", (Room(),))
    monkeypatch.setattr(dependencies, "PROJECT_ROOT", tmp_path)
    with pytest.raises(HTTPException) as captured:
        get_trusted_context_registry()
    assert captured.value.status_code == 503
    assert not (tmp_path / "config" / "tma_trusted_contexts").exists()


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
        __module__ = "aiogram.exceptions"

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



def test_reusable_context_denies_foreign_actor_via_membership(
    tmp_path: Path,
) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path)
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference
    foreign_user = {
        "id": 987654321,
        "first_name": "Foreign",
    }
    foreign_actor = validate_telegram_init_data(
        make_init_data(user=foreign_user, start_param=reference),
        BOT_TOKEN,
        now=AUTH_NOW,
    )

    class AllowingOnlyOriginalVerifier:
        async def check(self, chat_id: str, user_id: int):
            return TelegramMembershipDecision(
                status="member",
                allowed=user_id == USER["id"],
            )

    with pytest.raises(HTTPException) as captured:
        async_run(
            authorize_cafe_access(
                foreign_actor,
                reference,
                registry,
                AllowingOnlyOriginalVerifier(),
            )
        )
    assert captured.value.status_code == 403


def test_reusable_context_allows_multiple_authorized_members(
    tmp_path: Path,
) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path)
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference

    actor_a = validate_telegram_init_data(
        make_init_data(start_param=reference),
        BOT_TOKEN,
        now=AUTH_NOW,
    )
    actor_b = validate_telegram_init_data(
        make_init_data(
            user={
                "id": 987654321,
                "first_name": "Second",
            },
            start_param=reference,
        ),
        BOT_TOKEN,
        now=AUTH_NOW,
    )

    class AllowingVerifier:
        async def check(self, chat_id: str, user_id: int):
            return TelegramMembershipDecision(
                status="member",
                allowed=user_id in {123456789, 987654321},
            )

    for actor in (actor_a, actor_b):
        access = async_run(
            authorize_cafe_access(
                actor,
                reference,
                registry,
                AllowingVerifier(),
            )
        )
        assert access.context.reference == reference


def test_telegram_topic_entry_issues_real_opaque_context(
    tmp_path: Path,
) -> None:
    router = TelegramRoomRouter(tmp_path / "telegram_rooms.sqlite3")

    class Room:
        name = "#general"
        key = "general"
        external_id = "42"

    router.replace_chat_rooms("-100", (Room(),))
    registry = TrustedContextRegistry(
        router,
        store_dir=tmp_path / "contexts",
        max_age_seconds=3600,
    )

    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter._authority = SimpleNamespace(
        authorize=lambda _: SimpleNamespace(allowed=True, reason="")
    )
    adapter._room_router = router
    adapter._xp_tracker = SimpleNamespace(record_message=lambda *_: None)
    adapter._cafe_context_registry = registry
    adapter._cafe_bot_username_provider = lambda: "CafeOtakuBot"
    adapter._cafe_bot_username_cache = None

    command_update = {
        "message": {
            "from": {"id": 123456789},
            "chat": {"id": -100, "type": "supergroup"},
            "message_thread_id": 42,
            "is_topic_message": True,
            "text": "/cafe",
        }
    }
    prompt = adapter.handle_update(command_update)
    assert prompt.keyboard == (
        (("☕ Abrir Café", "cafe:open"),),
    )

    callback_update = {
        "callback_query": {
            "from": {"id": 123456789},
            "message": {
                "chat": {"id": -100},
                "message_thread_id": 42,
            },
            "data": "cafe:open",
        }
    }
    launch = adapter.handle_callback(callback_update)
    assert isinstance(launch, TelegramOutbound)
    assert launch.url_button is not None
    label, url = launch.url_button
    assert label == "☕ Abrir Café"
    assert url.startswith("https://t.me/CafeOtakuBot?startapp=tctx_")
    assert "-100" not in url
    assert "42" not in url
    assert "general" not in url
    payload = launch.payload()
    assert payload["reply_markup"]["inline_keyboard"][0][0]["url"] == url
    stored = registry.resolve(url.rsplit("=", 1)[1], now=AUTH_NOW)
    assert stored.chat_id == "-100"
    assert stored.message_thread_id == 42
    assert stored.room_key == "general"


def test_telegram_topic_unknown_route_cannot_issue_context(
    tmp_path: Path,
) -> None:
    router = TelegramRoomRouter(tmp_path / "telegram_rooms.sqlite3")
    registry = TrustedContextRegistry(
        router,
        store_dir=tmp_path / "contexts",
    )

    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter._room_router = router
    adapter._cafe_context_registry = registry
    adapter._cafe_bot_username_provider = lambda: "CafeOtakuBot"
    adapter._cafe_bot_username_cache = None

    result = adapter.handle_callback({
        "callback_query": {
            "from": {"id": 123456789},
            "message": {
                "chat": {"id": -100},
                "message_thread_id": 999,
            },
            "data": "cafe:open",
        }
    })
    assert "no está registrado" in result.text
    assert not any((tmp_path / "contexts").glob("*.json"))



def test_full_fastapi_pipeline_uses_real_room_router(
    tmp_path: Path,
    monkeypatch,
) -> None:
    routing_path = tmp_path / "config" / "telegram_rooms.sqlite3"
    routing_path.parent.mkdir(parents=True)
    writable = TelegramRoomRouter(routing_path)

    class Room:
        name = "#general"
        key = "general"
        external_id = "42"

    writable.replace_chat_rooms("-100", (Room(),))
    router = TelegramRoomRouter(routing_path, read_only=True)
    contexts = tmp_path / "config" / "tma_trusted_contexts"
    registry = TrustedContextRegistry(
        router,
        store_dir=contexts,
        create_store_dir=True,
    )
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference

    class AllowingVerifier:
        async def check(self, chat_id: str, user_id: int):
            assert chat_id == "-100"
            assert user_id == USER["id"]
            return TelegramMembershipDecision(
                status="member",
                allowed=True,
            )

    import api.dependencies as dependencies

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    app = FastAPI()
    app.dependency_overrides[dependencies.get_trusted_context_registry] = (
        lambda: registry
    )
    app.dependency_overrides[
        dependencies.get_telegram_membership_verifier
    ] = lambda: AllowingVerifier()

    @app.get("/cafe-real-router")
    async def cafe(access=Depends(get_current_cafe_access)):
        return {
            "actor_key": access.actor.actor_key,
            "room_key": access.context.room_key,
            "chat_id": access.context.chat_id,
            "message_thread_id": access.context.message_thread_id,
        }

    response = TestClient(app).get(
        "/cafe-real-router",
        headers={
            "Authorization": "tma "
            + make_init_data(start_param=reference),
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "actor_key": "telegram:123456789",
        "room_key": "general",
        "chat_id": "-100",
        "message_thread_id": 42,
    }


def test_full_fastapi_pipeline_allows_authorized_member(
    tmp_path: Path,
    monkeypatch,
) -> None:
    router = FakeRouter((FakeRoute("-100", 42, "general"),))
    registry = TrustedContextRegistry(router, store_dir=tmp_path / "contexts")
    reference = registry.issue("-100", 42, now=AUTH_NOW).reference

    class AllowingVerifier:
        async def check(self, chat_id: str, user_id: int):
            assert chat_id == "-100"
            assert user_id == USER["id"]
            return TelegramMembershipDecision(
                status="member",
                allowed=True,
            )

    import api.dependencies as dependencies

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)

    app = FastAPI()
    app.dependency_overrides[dependencies.get_trusted_context_registry] = (
        lambda: registry
    )
    app.dependency_overrides[
        dependencies.get_telegram_membership_verifier
    ] = lambda: AllowingVerifier()

    @app.get("/cafe")
    async def cafe(access=Depends(get_current_cafe_access)):
        return {
            "actor_key": access.actor.actor_key,
            "room_key": access.context.room_key,
            "message_thread_id": access.context.message_thread_id,
        }

    response = TestClient(app).get(
        "/cafe",
        headers={"Authorization": "tma " + make_init_data(start_param=reference)},
    )
    assert response.status_code == 200
    assert response.json() == {
        "actor_key": "telegram:123456789",
        "room_key": "general",
        "message_thread_id": 42,
    }


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
