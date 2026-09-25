from __future__ import annotations

import os

from aiogram import Bot

from app.core.module import BotModule
from app.db.database import Database
from app.multibot.vault_client import VaultClient


class SunnaNativeTriviaModule(BotModule):
    """Adapter that mounts the native image-trivia router into Sunna."""

    name = "sunna-native-trivia"

    def __init__(self, database: Database) -> None:
        super().__init__()
        from src.bot.handlers.trivia import build_trivia_router

        self.vault = VaultClient(
            os.getenv("CARD_VAULT_API_URL", "http://127.0.0.1:8765"),
            os.getenv("CARD_VAULT_TOKEN", ""),
        )
        self.router.include_router(build_trivia_router(database, self.vault))

    def setup(self) -> None:
        return

    async def on_startup(self, bot: Bot) -> None:
        await self.vault.start()

    async def on_shutdown(self) -> None:
        await self.vault.close()
        await super().on_shutdown()
