from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from urllib.parse import urljoin
from collections.abc import Callable


from aiohttp import web
from aiogram import Bot
from aiogram.types import LabeledPrice
from pydantic import ValidationError
from sqlalchemy import select

from app.api.dtos import (
    CombatActionDTO,
    CombatFighterDTO,
    CombatInitDTO,
    InvoiceRequestDTO,
    InvoiceResponseDTO,
    SpriteAssetDTO,
    TurnResultDTO,
)
from app.api.tma_auth import TmaAuthContext, TmaAuthError, init_data_from_request, validate_init_data
from app.core.access import is_authorized_community
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.core.time import utc_now
from app.db.database import Database
from app.db.models import GameCollection, GameProfile, SetupSession
from app.game.catalog import CHARACTERS, get_character
from app.game.java_engine import WaifuMonJavaEngine

logger = logging.getLogger(__name__)

TMA_API_VERSION = "1.0"
SPRITE_SIZE = 128
SPRITE_POSES = ("idle", "attack", "hit")
DEFAULT_FRONTEND_BASE = "https://eltiootaku01-hue.github.io/bot-telegram"


def _origins(settings: Settings) -> frozenset[str]:
    return frozenset(
        origin.strip().rstrip("/")
        for origin in settings.tma_allowed_origins.split(",")
        if origin.strip()
    )


def _json_error(status: int, code: str, message: str) -> web.Response:
    return web.json_response({"error": code, "message": message}, status=status)


def _asset_base(settings: Settings) -> str:
    base = settings.tma_frontend_base_url.strip() or DEFAULT_FRONTEND_BASE
    return base.rstrip("/") + "/"


def _asset_urls(settings: Settings, character_id: str) -> tuple[str, SpriteAssetDTO]:
    base = _asset_base(settings)
    card = urljoin(base, f"assets/production/cards/{character_id}--normal.jpg")
    sprites = SpriteAssetDTO(
        idle=urljoin(base, f"assets/production/sprites/{character_id}_idle.png"),
        attack=urljoin(base, f"assets/production/sprites/{character_id}_attack.png"),
        hit=urljoin(base, f"assets/production/sprites/{character_id}_hit.png"),
    )
    return card, sprites


def _fighter(settings: Settings, character_id: str, *, team: str, level: int = 1) -> CombatFighterDTO:
    character = get_character(character_id)
    card_url, sprites = _asset_urls(settings, character.id)
    return CombatFighterDTO(
        id=character.id,
        name=character.name,
        anime=character.anime,
        rarity=character.rarity.value,
        level=max(1, min(30, int(level))),
        team=team,
        card_url=card_url,
        sprites=sprites,
    )


class TmaCombatService:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        engine: WaifuMonJavaEngine | None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.engine = engine
        self._owns_engine = engine is None

    def _engine_client(self) -> WaifuMonJavaEngine:
        if self.engine is None:
            self.engine = WaifuMonJavaEngine()
        return self.engine

    def close(self) -> None:
        if self._owns_engine and self.engine is not None:
            self.engine.close()
            self.engine = None

    async def community_id(self) -> int:
        async with self.database.session() as session:
            setup = await session.scalar(
                select(SetupSession.chat_id)
                .where(
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
            )
        if setup is None:
            raise web.HTTPConflict(
                text='{"error":"COMMUNITY_NOT_CONFIGURED","message":"No hay una comunidad configurada."}',
                content_type="application/json",
            )
        chat_id = int(setup)
        if not is_authorized_community(self.settings, chat_id):
            raise web.HTTPForbidden(
                text='{"error":"COMMUNITY_NOT_AUTHORIZED","message":"La comunidad configurada no está autorizada."}',
                content_type="application/json",
            )
        return chat_id

    async def init(self, context: TmaAuthContext) -> CombatInitDTO:
        community_id = await self.community_id()
        async with self.database.session() as session:
            profile_id = await session.scalar(
                select(GameProfile.id).where(
                    GameProfile.user_id == context.user.id,
                    GameProfile.chat_id == community_id,
                )
            )
            owned_rows = []
            if profile_id is not None:
                owned_rows = list(
                    await session.scalars(
                        select(GameCollection)
                        .where(GameCollection.profile_id == profile_id)
                        .order_by(GameCollection.level.desc(), GameCollection.character_id.asc())
                        .limit(3)
                    )
                )

        team = [
            _fighter(self.settings, row.character_id, team="player", level=row.level)
            for row in owned_rows
            if row.character_id in CHARACTERS
        ]
        if not team:
            # Deterministic tutorial fighter; it is explicitly marked as demo.
            team = [_fighter(self.settings, "taiga", team="player", level=1)]

        opponent_ids = [
            character_id
            for character_id in sorted(CHARACTERS)
            if character_id not in {fighter.id for fighter in team}
        ]
        opponents = [
            _fighter(self.settings, character_id, team="enemy", level=1)
            for character_id in opponent_ids[:3]
        ]
        if not opponents:
            opponents = [_fighter(self.settings, team[0].id, team="enemy", level=1)]

        return CombatInitDTO(
            contract_version=TMA_API_VERSION,
            player_id=context.user.id,
            community_id=community_id,
            asset_contract={
                "card_directory": f"{_asset_base(self.settings)}assets/production/cards/",
                "sprite_directory": f"{_asset_base(self.settings)}assets/production/sprites/",
                "sprite_size": SPRITE_SIZE,
                "sprite_poses": list(SPRITE_POSES),
                "card_pattern": "<character-id>--normal.jpg",
                "sprite_pattern": "<character-id>_<idle|attack|hit>.png",
                "cut_in_duration_ms": 1500,
            },
            team=team,
            opponents=opponents,
        )

    async def action(self, context: TmaAuthContext, dto: CombatActionDTO) -> TurnResultDTO:
        community_id = await self.community_id()
        async with self.database.session() as session:
            profile_id = await session.scalar(
                select(GameProfile.id).where(
                    GameProfile.user_id == context.user.id,
                    GameProfile.chat_id == community_id,
                )
            )
            owned = False
            if profile_id is not None:
                owned = (
                    await session.scalar(
                        select(GameCollection.id).where(
                            GameCollection.profile_id == profile_id,
                            GameCollection.character_id == dto.attacker_id,
                        )
                    )
                ) is not None

        if not owned and not (profile_id is None and dto.attacker_id == "taiga"):
            raise web.HTTPForbidden(
                text='{"error":"ATTACKER_NOT_OWNED","message":"El atacante no pertenece al equipo del jugador."}',
                content_type="application/json",
            )
        if dto.attacker_id not in CHARACTERS or dto.defender_id not in CHARACTERS:
            raise web.HTTPBadRequest(
                text='{"error":"UNKNOWN_FIGHTER","message":"Combatiente inválido."}',
                content_type="application/json",
            )

        attacker = _fighter(self.settings, dto.attacker_id, team="player")
        defender = _fighter(self.settings, dto.defender_id, team="enemy")
        server_key = f"tma:{context.user.id}:{community_id}:{dto.idempotency_key}"
        result = self._engine_client().combat(
            attacker={
                "id": attacker.id,
                "name": attacker.name,
                "rarity": attacker.rarity,
                "level": attacker.level,
            },
            defender={
                "id": defender.id,
                "name": defender.name,
                "rarity": defender.rarity,
                "level": defender.level,
            },
            action=dto.action,
            turn_id=dto.turn_id,
            player_id=context.user.id,
            community_id=community_id,
            idempotency_key=server_key,
        )
        return TurnResultDTO(
            contract_version=TMA_API_VERSION,
            request_id=uuid.uuid4().hex,
            turn_id=dto.turn_id,
            attacker=result.attacker,
            defender=result.defender,
            action=result.action.key,
            damage=result.damage,
            critical=result.critical,
            defender_hp=result.defender_hp,
            defender_max_hp=100,
        )


class TmaApiServer:
    """Non-blocking aiohttp server owned by Bot Manager."""

    def __init__(
        self,
        settings: Settings,
        *,
        database: Database | None = None,
        engine: WaifuMonJavaEngine | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.engine = engine
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._thread_main,
            name="tma-api-server",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("TMA API server did not become ready")
        if self._error is not None:
            raise RuntimeError(f"TMA API server failed to start: {self._error}") from self._error

    def stop(self) -> None:
        loop = self._loop
        stop_event = self._stop_event
        thread = self._thread
        if loop is not None and stop_event is not None:
            loop.call_soon_threadsafe(stop_event.set)
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        self._thread = None
        self._loop = None
        self._stop_event = None

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._stop_event = asyncio.Event()
        try:
            loop.run_until_complete(self._serve())
        except BaseException as exc:
            self._error = exc
            self._ready.set()
            logger.exception("TMA API server stopped with an error")
        finally:
            loop.close()
            self._loop = None

    async def _serve(self) -> None:
        database = self.database or Database(self.settings.database_url)
        await database.create_schema()
        engine = self.engine
        app = create_tma_app(self.settings, database, engine)

        runner = web.AppRunner(app, access_log=logger)
        await runner.setup()
        site = web.TCPSite(runner, host=self.settings.tma_api_host, port=self.settings.tma_api_port)
        await site.start()
        self._ready.set()
        logger.info("TMA API listening on %s:%s", self.settings.tma_api_host, self.settings.tma_api_port)

        assert self._stop_event is not None
        try:
            await self._stop_event.wait()
        finally:
            await runner.cleanup()
            app["combat_service"].close()
            if self.database is None:
                await database.close()


def create_tma_app(
    settings: Settings,
    database: Database,
    engine: WaifuMonJavaEngine,
    *,
) -> web.Application:
    combat_service = TmaCombatService(database, settings, engine)
    app = web.Application(middlewares=[_tma_middleware(settings)])
    app["settings"] = settings
    app["database"] = database
    app["combat_service"] = combat_service
    app["invoice_bot_factory"] = invoice_bot_factory
    app.router.add_get("/api/combat/init", _combat_init)
    app.router.add_post("/api/combat/action", _combat_action)
    app.router.add_post("/api/store/invoice", _create_invoice)
    return app


def _tma_middleware(settings: Settings):
    @web.middleware
    async def middleware(request: web.Request, handler):
        origin = request.headers.get("Origin")
        allowed_origins = _origins(settings)
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            try:
                init_data = init_data_from_request(request)
                context = validate_init_data(
                    init_data,
                    settings.token_for(settings.tma_bot_identity.value),
                    max_age_seconds=settings.tma_init_data_max_age_seconds,
                )
            except (TmaAuthError, ValueError):
                return _json_error(401, "INVALID_TMA_AUTH", "Telegram initData no es válida.")
            request["tma_context"] = context
            response = await handler(request)

        if origin:
            if not allowed_origins or origin.rstrip("/") not in allowed_origins:
                return _json_error(403, "ORIGIN_NOT_ALLOWED", "Origen no autorizado.")
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return middleware


async def _combat_init(request: web.Request) -> web.Response:
    result = await request.app["combat_service"].init(request["tma_context"])
    return web.json_response(result.model_dump(mode="json"))


async def _combat_action(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        dto = CombatActionDTO.model_validate(payload)
    except (ValueError, ValidationError):
        return _json_error(400, "INVALID_BODY", "Cuerpo JSON de combate inválido.")
    try:
        result = await request.app["combat_service"].action(request["tma_context"], dto)
    except web.HTTPException as exc:
        return exc
    except ValueError as exc:
        return _json_error(409, "ENGINE_REJECTED", str(exc))
    except RuntimeError:
        logger.exception("WaifuMon Java engine failed")
        return _json_error(503, "ENGINE_UNAVAILABLE", "El motor de combate no está disponible.")
    return web.json_response(result.model_dump(mode="json"))


async def _create_invoice(request: web.Request) -> web.Response:
    try:
        dto = InvoiceRequestDTO.model_validate(await request.json())
    except (ValueError, ValidationError):
        return _json_error(400, "INVALID_BODY", "Producto inválido.")

    settings: Settings = request.app["settings"]
    token = settings.token_for(settings.tma_bot_identity.value)
    if not token:
        return _json_error(503, "PAYMENTS_UNAVAILABLE", "El bot de pagos no está configurado.")

    prices = {
        "premium_ticket": (
            settings.tma_premium_ticket_price_stars,
            "Ticket Premium",
            "Ticket Premium para WaifuMon",
        ),
        "starter_pack": (
            settings.tma_starter_pack_price_stars,
            "Starter Pack",
            "Pack inicial digital de WaifuMon",
        ),
    }
    amount, title, description = prices[dto.product]
    if amount <= 0:
        return _json_error(503, "INVALID_PRICE", "El precio del producto no está configurado.")

    context: TmaAuthContext = request["tma_context"]
    payload = f"tma:{context.user.id}:{dto.product}:{uuid.uuid4().hex}"
    bot_factory = request.app.get("invoice_bot_factory")
    bot = bot_factory(token) if bot_factory is not None else Bot(token=token)
    try:
        invoice_link = await bot.create_invoice_link(
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=amount)],
        )
    finally:
        await bot.session.close()

    response = InvoiceResponseDTO(
        product=dto.product,
        currency="XTR",
        amount=amount,
        invoice_link=invoice_link,
        payload=payload,
    )
    return web.json_response(response.model_dump(mode="json"))
