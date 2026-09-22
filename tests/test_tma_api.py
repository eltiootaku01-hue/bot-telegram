from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app.api.dtos import CombatAssetContractDTO, TurnResultDTO
from app.api.tma_auth import validate_init_data
from app.api.tma_server import create_tma_app
from app.core.config import Settings
from app.db.database import Database
from app.db.community_models import SetupSession
from app.db.models import Chat, GameProfile, User
from app.game.models import CombatAction, CombatResult


BOT_TOKEN = "123456:TEST_TOKEN"
USER_ID = 777


def make_init_data(*, auth_date: int | None = None, user_id: int = USER_ID) -> str:
    user = {
        "id": user_id,
        "first_name": "Johan",
        "username": "tester",
        "language_code": "es",
    }
    values = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAE-test-query",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
        "signature": "telegram-third-party-signature-placeholder",
    }
    data_check_string = "\n".join(
        f"{key}={values[key]}" for key in sorted(values)
    )
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=BOT_TOKEN.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    digest = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    values["hash"] = digest
    return urlencode(values)


def test_validate_init_data_accepts_valid_telegram_signature() -> None:
    context = validate_init_data(make_init_data(), BOT_TOKEN, now=int(time.time()))
    assert context.user.id == USER_ID
    assert context.user.first_name == "Johan"


def test_validate_init_data_rejects_tampered_payload() -> None:
    init_data = make_init_data().replace("Johan", "Intruder")
    with pytest.raises(ValueError, match="HMAC"):
        validate_init_data(init_data, BOT_TOKEN, now=int(time.time()))


def test_validate_init_data_covers_signature_field_in_bot_hash() -> None:
    context = validate_init_data(make_init_data(), BOT_TOKEN, now=int(time.time()))
    assert context.user.id == USER_ID


def test_validate_init_data_rejects_stale_auth_date() -> None:
    stale = int(time.time()) - 7200
    with pytest.raises(ValueError, match="expired"):
        validate_init_data(
            make_init_data(auth_date=stale),
            BOT_TOKEN,
            max_age_seconds=3600,
            now=int(time.time()),
        )


@pytest.mark.asyncio
async def test_tma_endpoint_authentication_covers_store_and_combat_actions() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
        tma_allowed_origins="https://example.github.io",
    )
    app = create_tma_app(settings, database, FakeEngine())

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            checks = [
                await client.get(
                    "/api/combat/init",
                    headers={"Origin": "https://example.github.io"},
                ),
                await client.post(
                    "/api/combat/action",
                    headers={"Origin": "https://example.github.io"},
                    json={},
                ),
                await client.post(
                    "/api/store/invoice",
                    headers={"Origin": "https://example.github.io"},
                    json={"product": "premium_ticket"},
                ),
            ]
            assert [response.status for response in checks] == [401, 401, 401]
        finally:
            await client.close()
    await database.close()


@pytest.mark.asyncio
async def test_tma_action_offloads_blocking_java_call() -> None:
    import asyncio
    import time

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as session:
        session.add(
            SetupSession(
                user_id=USER_ID,
                chat_id=-100123,
                bot_identity="chie",
                status="configured",
            )
        )

    class SlowEngine(FakeEngine):
        def combat(self, **kwargs):
            time.sleep(0.15)
            return super().combat(**kwargs)

        async def combat_async(self, **kwargs):
            return await asyncio.to_thread(self.combat, **kwargs)

    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
    )
    app = create_tma_app(settings, database, SlowEngine())

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        ticks = 0

        async def ticker():
            nonlocal ticks
            deadline = asyncio.get_running_loop().time() + 0.10
            while asyncio.get_running_loop().time() < deadline:
                ticks += 1
                await asyncio.sleep(0.005)

        request_task = asyncio.create_task(
            client.post(
                "/api/combat/action",
                headers={"X-Telegram-Init-Data": make_init_data()},
                json={
                    "action": "attack",
                    "attacker_id": "taiga",
                    "defender_id": "anya",
                    "turn_id": "nonblocking-turn",
                    "idempotency_key": "nonblocking-idem",
                },
            )
        )
        ticker_task = asyncio.create_task(ticker())
        response, _ = await asyncio.gather(request_task, ticker_task)
        assert response.status == 200
        assert ticks >= 5
        await client.close()

    await database.close()


def test_combat_asset_contract_is_typed() -> None:
    contract = CombatAssetContractDTO(
        card_directory="https://example.test/cards/",
        sprite_directory="https://example.test/sprites/",
        sprite_size=128,
        sprite_poses=["idle", "attack", "hit"],
        card_pattern="<character-id>--normal.jpg",
        sprite_pattern="<character-id>_<idle|attack|hit>.png",
        cut_in_duration_ms=1500,
    )
    assert contract.sprite_size == 128
    assert contract.sprite_poses == ["idle", "attack", "hit"]



@pytest.mark.asyncio
async def test_tma_rejects_disallowed_origin_even_with_valid_init_data() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
        tma_allowed_origins="https://allowed.example",
    )
    app = create_tma_app(settings, database, FakeEngine())

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.get(
                "/api/combat/init",
                headers={
                    "Origin": "https://evil.example",
                    "X-Telegram-Init-Data": make_init_data(),
                },
            )
            assert response.status == 403
            payload = await response.json()
            assert payload["error"] == "ORIGIN_NOT_ALLOWED"
        finally:
            await client.close()

    await database.close()


@pytest.mark.asyncio
async def test_tma_options_is_cors_preflight_and_does_not_execute_business_logic() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
        tma_allowed_origins="https://allowed.example",
    )
    app = create_tma_app(settings, database, FakeEngine())

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.options(
                "/api/combat/action",
                headers={
                    "Origin": "https://allowed.example",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type,x-telegram-init-data",
                },
            )
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Origin"] == "https://allowed.example"
        finally:
            await client.close()

    await database.close()


class FakeEngine:
    def __init__(self) -> None:
        self.calls = []

    def combat(self, **kwargs):
        self.calls.append(kwargs)
        return CombatResult(
            attacker=kwargs["attacker"]["name"],
            defender=kwargs["defender"]["name"],
            damage=23,
            action=CombatAction(kwargs["action"], kwargs["action"], 10),
            critical=False,
            defender_hp=77,
        )

    async def combat_async(self, **kwargs):
        return self.combat(**kwargs)


class FakeBot:
    def __init__(self) -> None:
        self.calls = []
        self.session = self

    async def create_invoice_link(self, **kwargs):
        self.calls.append(kwargs)
        return "https://t.me/invoice/test"

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_tma_routes_require_init_data_and_delegate_combat() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as session:
        session.add(SetupSession(
            user_id=USER_ID,
            chat_id=-100123,
            bot_identity="chie",
            status="configured",
        ))

    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
        tma_frontend_base_url="https://example.github.io/bot-telegram",
    )
    engine = FakeEngine()
    app = create_tma_app(settings, database, engine)

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            unauthenticated = await client.get("/api/combat/init")
            assert unauthenticated.status == 401

            init_response = await client.get(
                "/api/combat/init",
                headers={"X-Telegram-Init-Data": make_init_data()},
            )
            assert init_response.status == 200
            payload = await init_response.json()
            assert payload["player_id"] == USER_ID
            assert payload["community_id"] == -100123
            assert payload["asset_contract"]["sprite_size"] == 128
            assert payload["asset_contract"]["cut_in_duration_ms"] == 1500
            assert payload["team"][0]["sprites"]["idle"].endswith(
                "/assets/production/sprites/taiga_idle.png"
            )

            action_response = await client.post(
                "/api/combat/action",
                headers={"X-Telegram-Init-Data": make_init_data()},
                json={
                    "action": "special",
                    "attacker_id": "taiga",
                    "defender_id": "taiga",
                    "turn_id": "turn-1",
                    "idempotency_key": "button-1",
                },
            )
            assert action_response.status == 200
            result = await action_response.json()
            TurnResultDTO.model_validate(result)
            assert result["action"] == "special"
            assert result["damage"] == 23
            assert engine.calls[0]["player_id"] == USER_ID
            assert engine.calls[0]["community_id"] == -100123
            assert engine.calls[0]["idempotency_key"].startswith("tma:777:-100123:")
        finally:
            await client.close()

    await database.close()


@pytest.mark.asyncio
async def test_invoice_endpoint_uses_xtr_and_backend_identity() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as session:
        session.add(SetupSession(
            user_id=USER_ID,
            chat_id=-100123,
            bot_identity="chie",
            status="configured",
        ))

    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
        tma_premium_ticket_price_stars=10,
    )
    engine = FakeEngine()
    fake_bot = FakeBot()
    app = create_tma_app(
        settings,
        database,
        engine,
        invoice_bot_factory=lambda token: fake_bot,
    )

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.post(
                "/api/store/invoice",
                headers={"X-Telegram-Init-Data": make_init_data()},
                json={"product": "premium_ticket"},
            )
            assert response.status == 200
            payload = await response.json()
            assert payload["currency"] == "XTR"
            assert payload["amount"] == 10
            assert payload["invoice_link"] == "https://t.me/invoice/test"
            assert fake_bot.calls[0]["currency"] == "XTR"
            assert "provider_token" not in fake_bot.calls[0]
            assert len(fake_bot.calls[0]["prices"]) == 1
            assert fake_bot.calls[0]["prices"][0].label == "Ticket Premium"
            assert fake_bot.calls[0]["prices"][0].amount == 10
        finally:
            await client.close()

    await database.close()


@pytest.mark.asyncio
async def test_tma_tutorial_allows_empty_existing_profile() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as session:
        session.add(User(id=USER_ID, first_name="Johan"))
        session.add(Chat(id=-100123, type="supergroup", title="Test"))
        await session.flush()
        session.add(
            SetupSession(
                user_id=USER_ID,
                chat_id=-100123,
                bot_identity="chie",
                status="configured",
            )
        )
        session.add(GameProfile(user_id=USER_ID, chat_id=-100123))

    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
    )
    engine = FakeEngine()
    app = create_tma_app(settings, database, engine)

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.post(
                "/api/combat/action",
                headers={"X-Telegram-Init-Data": make_init_data()},
                json={
                    "action": "attack",
                    "attacker_id": "taiga",
                    "defender_id": "anya",
                    "turn_id": "tutorial-existing-profile",
                    "idempotency_key": "tutorial-idem",
                },
            )
            assert response.status == 200
            payload = await response.json()
            assert payload["attacker"] == "Taiga Aisaka"
            assert engine.calls[0]["attacker"]["level"] == 1
        finally:
            await client.close()

    await database.close()


@pytest.mark.asyncio
async def test_tma_action_reaches_real_java_engine() -> None:
    from pathlib import Path

    from app.game.java_engine import EngineClientConfig, WaifuMonJavaEngine

    root = Path(__file__).resolve().parents[1]
    jar = root / "engine" / "waifumon" / "target" / "waifumon-engine.jar"
    if not jar.exists():
        pytest.skip("Java engine must be built before TMA integration test")

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    async with database.session() as session:
        session.add(
            SetupSession(
                user_id=USER_ID,
                chat_id=-100123,
                bot_identity="chie",
                status="configured",
            )
        )

    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
        tma_frontend_base_url="https://example.github.io/bot-telegram",
    )
    engine = WaifuMonJavaEngine(
        config=EngineClientConfig(jar_path=jar, java_command="java")
    )
    app = create_tma_app(settings, database, engine)

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.post(
                "/api/combat/action",
                headers={"X-Telegram-Init-Data": make_init_data()},
                json={
                    "action": "attack",
                    "attacker_id": "taiga",
                    "defender_id": "anya",
                    "turn_id": "real-java-turn",
                    "idempotency_key": "real-java-idem",
                },
            )
            assert response.status == 200
            payload = await response.json()
            result = TurnResultDTO.model_validate(payload)
            assert result.contract_version == "1.0"
            assert result.turn_id == "real-java-turn"
            assert result.damage >= 1
            assert result.defender_hp >= 0
        finally:
            await client.close()

    engine.close()
    await database.close()



@pytest.mark.asyncio
async def test_admin_card_upload_creates_definition_and_persists_image(tmp_path) -> None:
    from aiohttp import FormData

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        admin_user_id=USER_ID,
        authorized_chat_ids="-100123",
        tma_bot_identity="sunna",
        card_assets_dir=str(tmp_path / "card-assets"),
    )
    app = create_tma_app(settings, database, FakeEngine())

    form = FormData()
    form.add_field("character-name", "Asuna (Verano)")
    form.add_field("character-id", "asuna")
    form.add_field("anime-origin", "Sword Art Online")
    form.add_field("rarity", "SSR")
    form.add_field("source-provider", "IA (PixAI/Midjourney)")
    form.add_field("collection-points", "150")
    form.add_field(
        "image",
        b"\xff\xd8\xff\xe0fake-jpeg",
        filename="asuna_summer_ssr.jpg",
        content_type="image/jpeg",
    )

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.post(
                "/api/admin/cards",
                headers={"X-Telegram-Init-Data": make_init_data(user_id=USER_ID)},
                data=form,
            )
            assert response.status == 201
            payload = await response.json()
            assert payload["character_id"] == "asuna"
            assert payload["character_name"] == "Asuna (Verano)"
            assert payload["anime_origin"] == "Sword Art Online"
            assert payload["rarity"] == "SSR"
            assert payload["image_url"].startswith("assets/cards/")
            assert payload["source_provider"] == "IA (PixAI/Midjourney)"
            assert payload["collection_points"] == 150
            filename = payload["image_url"].rsplit("/", 1)[-1]

            asset_response = await client.get(f"/api/cards/assets/{filename}")
            assert asset_response.status == 200
            assert await asset_response.read() == b"\xff\xd8\xff\xe0fake-jpeg"

            listing = await client.get(
                "/api/admin/cards",
                headers={"X-Telegram-Init-Data": make_init_data(user_id=USER_ID)},
            )
            assert listing.status == 200
            cards = (await listing.json())["cards"]
            assert any(card["id"] == payload["id"] for card in cards)
        finally:
            await client.close()

    await database.close()


@pytest.mark.asyncio
async def test_admin_card_endpoint_rejects_non_admin(tmp_path) -> None:
    from aiohttp import FormData

    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_schema()
    settings = Settings(
        bot_token_sunna=BOT_TOKEN,
        admin_user_id=USER_ID,
        card_assets_dir=str(tmp_path / "card-assets"),
    )
    app = create_tma_app(settings, database, FakeEngine())

    form = FormData()
    form.add_field("character-name", "Intruso")
    form.add_field("anime-origin", "Test")
    form.add_field("rarity", "C")
    form.add_field("image", b"\xff\xd8\xff", filename="x.jpg", content_type="image/jpeg")

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            response = await client.post(
                "/api/admin/cards",
                headers={"X-Telegram-Init-Data": make_init_data(user_id=USER_ID + 1)},
                data=form,
            )
            assert response.status == 403
            payload = await response.json()
            assert payload["error"] == "ADMIN_REQUIRED"
        finally:
            await client.close()

    await database.close()
