from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import pytest

from app.multibot.vault_client import VaultClient


@pytest.mark.asyncio
async def test_vault_client_uses_non_blocking_compatibility_contract() -> None:
    calls: list[tuple[str, dict]] = []

    async def inventory(request: web.Request) -> web.Response:
        calls.append(("inventory", dict(request.query)))
        return web.json_response(
            {"items": [{"card_id": "c1", "card_code": "#001", "quantity": 2}]}
        )

    async def locks(request: web.Request) -> web.Response:
        calls.append(("lock", dict(request.query)))
        return web.json_response(
            {"items": [{"card_id": "c1", "quantity": 2, "locked_quantity": 1, "available_quantity": 1}]}
        )

    async def transfer(request: web.Request) -> web.Response:
        body = await request.json()
        calls.append(("transfer", body))
        return web.json_response(
            {"transaction_id": 7, "idempotency_key": body["idempotency_key"], "card_delta": -1, "coin_delta": 0}
        )

    app = web.Application()
    app.router.add_get("/api/inventory/{user_id}", inventory)
    app.router.add_get("/api/cards/lock-status", locks)
    app.router.add_post("/api/cards/transfer", transfer)

    async with TestServer(app) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            vault = VaultClient(str(server.make_url("/")).rstrip("/"))

            assert await vault.inventory(42) == [
                {"card_id": "c1", "card_code": "#001", "quantity": 2}
            ]
            assert await vault.lock_status(holder_key="42", card_id="c1") == [
                {
                    "card_id": "c1",
                    "quantity": 2,
                    "locked_quantity": 1,
                    "available_quantity": 1,
                }
            ]
            result = await vault.transfer(
                card_id="c1",
                from_type="bank",
                from_key="main-bank",
                to_type="user",
                to_key="42",
                quantity=1,
                actor_user_id=42,
                idempotency_key="test-roll-1",
            )
            assert result["idempotency_key"] == "test-roll-1"

            assert calls[0] == ("inventory", {})
            assert calls[1] == (
                "lock",
                {"holder_type": "user", "holder_key": "42", "card_id": "c1"},
            )
            assert calls[2][0] == "transfer"
            assert calls[2][1]["idempotency_key"] == "test-roll-1"
        finally:
            await client.close()
