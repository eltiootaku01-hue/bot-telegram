from __future__ import annotations

import asyncio

from app.card_vault.api import VaultApiServer
from app.card_vault.service import CardVaultService
from app.core.config import get_settings
from app.db.database import Database


async def run() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    await database.create_schema()
    service = CardVaultService(
        asset_root=settings.card_asset_root,
        thumbnail_root=settings.card_thumbnail_root,
    )
    api = VaultApiServer(
        database,
        service,
        token=settings.vault_api_token,
        host="127.0.0.1",
        port=8766,
    )
    await api.start()
    try:
        await asyncio.Event().wait()
    finally:
        await api.stop()
        await database.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
