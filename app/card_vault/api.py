from __future__ import annotations

import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aiohttp import web

from app.card_vault.contracts import CardRegistration, CardRarity
from app.card_vault.service import CardVaultService
from app.db.database import Database
from app.db.card_vault_models import CardHolderType


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

    async def start(self) -> None:
        app = web.Application(middlewares=[self._auth])
        app.router.add_get("/healthz", self._health)
        app.router.add_post("/v1/cards", self._register_card)
        app.router.add_get("/v1/inventory", self._inventory)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
