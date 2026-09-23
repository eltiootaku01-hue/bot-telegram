from __future__ import annotations

import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from aiohttp import web

from app.card_vault.contracts import CardRegistration, CardRarity
from app.card_vault.service import CardVaultService
from app.db.database import Database
from app.db.models import CardDefinition
from app.db.card_vault_models import CardHolderType, CardInventory, TransactionHistory


class VaultApiServer:
    """Loopback-only HTTP API for Casa de Comando -> local card vault calls."""

    def __init__(
        self,
        database: Database,
        service: CardVaultService,
        *,
        token: str,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.database = database
        self.service = service
        self.token = token
        self.host = host
        self.port = port
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    def _authorized(self, request: web.Request) -> bool:
        if not self.token:
            return request.remote in {"127.0.0.1", "::1"}
        candidate = request.headers.get("Authorization", "")
        if not candidate.startswith("Bearer "):
            return False
        return secrets.compare_digest(candidate[7:], self.token)

    @web.middleware
    async def _auth(self, request: web.Request, handler) -> web.StreamResponse:
        if request.path == "/healthz":
            return await handler(request)
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "card-vault"})

    async def _register_card(self, request: web.Request) -> web.Response:
        body: dict[str, Any] = await request.json()
        card = CardRegistration(
            card_id=str(body["card_id"]),
            card_code=str(body["card_code"]),
            character_id=str(body["character_id"]),
            character_name=str(body["character_name"]),
            anime_origin=str(body["anime_origin"]),
            rarity=CardRarity(str(body["rarity"])),
            asset_path=Path(str(body["asset_path"])),
            source_provider=str(body.get("source_provider") or "local"),
            collection_points=int(body.get("collection_points") or 0),
            custom_emoji_id=str(body.get("custom_emoji_id") or "") or None,
        )
        async with self.database.session() as session:
            row = await self.service.register_card(session, card)
        return web.json_response({
            "id": row.id,
            "card_code": row.card_code,
            "asset_path": row.asset_path,
            "thumbnail_path": row.thumbnail_path,
            "coin_value": row.coin_value,
            "telegram_protected": row.telegram_protected,
        })

    async def _transfer(self, request: web.Request) -> web.Response:
        body: dict[str, Any] = await request.json()
        from_type = CardHolderType(str(body["from_type"]))
        to_type = CardHolderType(str(body["to_type"]))
        async with self.database.session() as session:
            result = await self.service.transfer(
                session,
                card_id=str(body["card_id"]),
                from_type=from_type,
                from_key=str(body["from_key"]),
                to_type=to_type,
                to_key=str(body["to_key"]),
                quantity=int(body["quantity"]),
                actor_user_id=int(body["actor_user_id"]) if body.get("actor_user_id") is not None else None,
                reference_id=str(body["reference_id"]),
            )
        return web.json_response(asdict(result))

    async def _inventory(self, request: web.Request) -> web.Response:
        holder_type = CardHolderType(request.query["holder_type"])
        holder_key = request.query["holder_key"]
        async with self.database.session() as session:
            rows = await self.service.inventory(
                session,
                holder_type=holder_type,
                holder_key=holder_key,
            )
        return web.json_response({"items": [asdict(row) for row in rows]})


    async def _cards(self, request: web.Request) -> web.Response:
        active_only = request.query.get("active_only", "true").lower() != "false"
        async with self.database.session() as session:
            statement = select(CardDefinition).order_by(
                CardDefinition.card_code.asc(),
                CardDefinition.id.asc(),
            )
            if active_only:
                statement = statement.where(CardDefinition.active.is_(True))
            rows = list(await session.scalars(statement))
        return web.json_response(
            {
                "cards": [
                    {
                        "id": row.id,
                        "card_code": row.card_code,
                        "character_id": row.character_id,
                        "character_name": row.character_name,
                        "anime_origin": row.anime_origin,
                        "rarity": row.rarity,
                        "coin_value": row.coin_value,
                        "collection_points": row.collection_points,
                        "telegram_protected": row.telegram_protected,
                        "custom_emoji_id": row.custom_emoji_id,
                    }
                    for row in rows
                ]
            }
        )

    async def _lock_status(self, request: web.Request) -> web.Response:
        holder_type = CardHolderType(
            request.query.get("holder_type", CardHolderType.USER.value)
        )
        holder_key = request.query["holder_key"]
        card_id = request.query.get("card_id")
        async with self.database.session() as session:
            statement = select(CardInventory).where(
                CardInventory.holder_type == holder_type.value,
                CardInventory.holder_key == holder_key,
            )
            if card_id:
                statement = statement.where(CardInventory.card_id == card_id)
            rows = list(await session.scalars(statement))
        return web.json_response(
            {
                "items": [
                    {
                        "card_id": row.card_id,
                        "quantity": row.quantity,
                        "locked_quantity": row.locked_quantity,
                        "available_quantity": row.quantity - row.locked_quantity,
                    }
                    for row in rows
                ]
            }
        )

    async def _balance(self, request: web.Request) -> web.Response:
        user_id = int(request.match_info["user_id"])
        async with self.database.session() as session:
            total = await session.scalar(
                select(func.coalesce(func.sum(TransactionHistory.coin_delta), 0)).where(
                    TransactionHistory.target_user_id == user_id
                )
            )
        return web.json_response({"user_id": user_id, "balance": int(total or 0)})

    async def _inventory_user(self, request: web.Request) -> web.Response:
        holder_key = request.match_info["user_id"]
        async with self.database.session() as session:
            rows = await self.service.inventory(
                session,
                holder_type=CardHolderType.USER,
                holder_key=holder_key,
            )
        return web.json_response({"items": [asdict(row) for row in rows]})

    async def _transfer_compat(self, request: web.Request) -> web.Response:
        body = dict(await request.json())
        if "reference_id" not in body:
            body["reference_id"] = str(body.get("idempotency_key", ""))
        if not body["reference_id"]:
            raise web.HTTPBadRequest(text="idempotency_key is required")
        from_type = CardHolderType(str(body["from_type"]))
        to_type = CardHolderType(str(body["to_type"]))
        async with self.database.session() as session:
            result = await self.service.transfer(
                session,
                card_id=str(body["card_id"]),
                from_type=from_type,
                from_key=str(body["from_key"]),
                to_type=to_type,
                to_key=str(body["to_key"]),
                quantity=int(body["quantity"]),
                actor_user_id=(
                    int(body["actor_user_id"])
                    if body.get("actor_user_id") is not None
                    else None
                ),
                reference_id=str(body["reference_id"]),
            )
        return web.json_response(asdict(result))

    def create_app(self) -> web.Application:
        app = web.Application(middlewares=[self._auth])
        app.router.add_get("/healthz", self._health)
        app.router.add_post("/v1/cards", self._register_card)
        app.router.add_post("/v1/transfer", self._transfer)
        app.router.add_get("/v1/inventory", self._inventory)
        app.router.add_get("/v1/cards", self._cards)
        app.router.add_get("/v1/lock-status", self._lock_status)
        app.router.add_get("/v1/balance/{user_id}", self._balance)
        app.router.add_get("/api/inventory/{user_id}", self._inventory_user)
        app.router.add_get("/api/cards/lock-status", self._lock_status)
        app.router.add_post("/api/cards/transfer", self._transfer_compat)
        app.router.add_get("/api/balance/{user_id}", self._balance)
        return app

    async def start(self) -> None:
        app = self.create_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
