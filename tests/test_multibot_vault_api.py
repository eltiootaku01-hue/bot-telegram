from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app.card_vault.api import VaultApiServer
from app.card_vault.contracts import CardRegistration, CardRarity
from app.card_vault.service import CardVaultService
from app.db.card_vault_models import CardHolderType
from app.db.database import Database
from app.db.models import User


@pytest.mark.asyncio
async def test_multibot_vault_compatibility_routes(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'vault-api.db'}")
    await database.create_schema()
    service = CardVaultService(tmp_path / "assets", tmp_path / "thumbs")

    source = tmp_path / "rei.png"
    from PIL import Image

    Image.new("RGB", (64, 64), "white").save(source)

    async with database.session() as session:
        session.add(User(id=42, first_name="Test"))
        await session.flush()
        card = await service.register_card(
            session,
            CardRegistration(
                card_id="rei-compat",
                card_code="#901",
                character_id="rei",
                character_name="Rei Ayanami",
                anime_origin="Neon Genesis Evangelion",
                rarity=CardRarity.R,
                asset_path=source,
            ),
        )
        await service.adjust_inventory(
            session,
            card_id=card.id,
            holder_type=CardHolderType.BANK,
            holder_key="main-bank",
            delta=2,
        )

    api = VaultApiServer(database, service, token="")
    async with TestServer(api.create_app()) as server:
        client = TestClient(server)
        await client.start_server()
        try:
            inventory = await client.get("/api/inventory/42")
            assert inventory.status == 200
            assert (await inventory.json())["items"] == []

            lock_status = await client.get(
                "/api/cards/lock-status",
                params={"holder_type": "bank", "holder_key": "main-bank"},
            )
            assert lock_status.status == 200
            assert (await lock_status.json())["items"][0]["available_quantity"] == 2

            transfer = await client.post(
                "/api/cards/transfer",
                json={
                    "card_id": "rei-compat",
                    "from_type": "bank",
                    "from_key": "main-bank",
                    "to_type": "user",
                    "to_key": "42",
                    "quantity": 1,
                    "actor_user_id": 42,
                    "idempotency_key": "compat-roll-1",
                },
            )
            assert transfer.status == 200
            body = await transfer.json()
            assert body["card_delta"] == -1

            replay = await client.post(
                "/api/cards/transfer",
                json={
                    "card_id": "rei-compat",
                    "from_type": "bank",
                    "from_key": "main-bank",
                    "to_type": "user",
                    "to_key": "42",
                    "quantity": 1,
                    "actor_user_id": 42,
                    "idempotency_key": "compat-roll-1",
                },
            )
            assert replay.status == 200
            assert await replay.json() == body

            user_inventory = await client.get("/api/inventory/42")
            rows = (await user_inventory.json())["items"]
            assert rows[0]["card_code"] == "#901"
            assert rows[0]["quantity"] == 1
        finally:
            await client.close()

    await database.close()
