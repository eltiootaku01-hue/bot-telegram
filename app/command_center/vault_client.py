from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import aiohttp

from app.card_vault.contracts import CardRegistration


class CardVaultClient:
    """Async client for the loopback-only Card Vault API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8765",
        token: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def health(self) -> dict:
        async with aiohttp.ClientSession(headers=self._headers()) as http:
            async with http.get(f"{self.base_url}/healthz") as response:
                response.raise_for_status()
                return await response.json()

    async def register_card(self, card: CardRegistration) -> dict:
        payload = asdict(card)
        payload["rarity"] = card.rarity.value
        payload["asset_path"] = str(Path(card.asset_path).resolve())
        async with aiohttp.ClientSession(headers=self._headers()) as http:
            async with http.post(f"{self.base_url}/v1/cards", json=payload) as response:
                response.raise_for_status()
                return await response.json()

    async def inventory(self, holder_type: str, holder_key: str) -> list[dict]:
        async with aiohttp.ClientSession(headers=self._headers()) as http:
            async with http.get(
                f"{self.base_url}/v1/inventory",
                params={"holder_type": holder_type, "holder_key": holder_key},
            ) as response:
                response.raise_for_status()
                body = await response.json()
                return list(body["items"])

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
        reference_id: str,
    ) -> dict:
        payload = {
            "card_id": card_id,
            "from_type": from_type,
            "from_key": from_key,
            "to_type": to_type,
            "to_key": to_key,
            "quantity": quantity,
            "actor_user_id": actor_user_id,
            "reference_id": reference_id,
        }
        async with aiohttp.ClientSession(headers=self._headers()) as http:
            async with http.post(f"{self.base_url}/v1/transfer", json=payload) as response:
                response.raise_for_status()
                return await response.json()
