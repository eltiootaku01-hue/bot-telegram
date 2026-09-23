from __future__ import annotations

from typing import Any

import aiohttp


class VaultClient:
    """Non-blocking client for the local Card Vault API."""

    def __init__(
        self,
        base_url: str,
        token: str = "",
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers,
        ) as session:
            async with session.request(method, f"{self.base_url}{path}", **kwargs) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(f"Vault API {response.status}: {body[:500]}")
                return await response.json()

    async def inventory(self, user_id: int) -> list[dict[str, Any]]:
        payload = await self._request("GET", f"/api/inventory/{user_id}")
        return list(payload.get("items", []))

    async def catalog(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/v1/cards")
        return list(payload.get("cards", []))

    async def lock_status(
        self,
        *,
        holder_type: str = "user",
        holder_key: str,
        card_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {"holder_type": holder_type, "holder_key": holder_key}
        if card_id:
            params["card_id"] = card_id
        payload = await self._request("GET", "/api/cards/lock-status", params=params)
        return list(payload.get("items", []))

    async def transfer(
        self,
        *,
        card_id: str,
        from_type: str,
        from_key: str,
        to_type: str,
        to_key: str,
        quantity: int,
        actor_user_id: int | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        payload = {
            "card_id": card_id,
            "from_type": from_type,
            "from_key": from_key,
            "to_type": to_type,
            "to_key": to_key,
            "quantity": quantity,
            "actor_user_id": actor_user_id,
            "idempotency_key": idempotency_key,
        }
        return await self._request("POST", "/api/cards/transfer", json=payload)

    async def balance(self, user_id: int) -> int:
        payload = await self._request("GET", f"/api/balance/{user_id}")
        return int(payload.get("balance", 0))

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/healthz")
