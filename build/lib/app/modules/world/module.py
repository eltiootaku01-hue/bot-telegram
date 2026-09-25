from __future__ import annotations

from aiogram import Bot

from app.core.module import BotModule
from app.db.database import Database
from app.services.world import WorldService


class WorldCatalogModule(BotModule):
    """Initialize the approved Ciudad Animals catalog for every bot process."""

    name = "world-catalog"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.world = WorldService()

    def setup(self) -> None:
        return None

    async def on_startup(self, bot: Bot) -> None:
        async with self.database.session() as session:
            await self.world.seed_catalog(session)
