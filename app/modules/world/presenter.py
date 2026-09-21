from __future__ import annotations

from aiogram import Bot

from app.core.config import Settings
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.database import Database
from app.world.presenter import WorldPresenter
from app.world.runtime import WorldRuntime


class WorldPresentationModule(BotModule):
    """Bridge one Telegram bot identity to the independent world presenter loop."""

    name = "world-runtime"

    def __init__(
        self,
        database: Database,
        identity: BotIdentity,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self.database = database
        self.identity = identity
        self.settings = settings
        self.runtime: WorldRuntime | None = None

    def setup(self) -> None:
        return None

    async def on_startup(self, bot: Bot) -> None:
        async def send(presenter_key: str, chat_id: int, text: str) -> int:
            if presenter_key != self.identity.value:
                raise RuntimeError(
                    f"World event addressed to presenter {presenter_key!r}, "
                    f"but this process owns {self.identity.value!r}"
                )
            sent = await bot.send_message(chat_id, text)
            return sent.message_id

        presenter = WorldPresenter(send)
        self.runtime = WorldRuntime(
            self.database,
            presenter,
            settings=self.settings,
            presenter_key=f"existing_bot:{self.identity.value}",
        )
        self.tasks.start(f"world-runtime-{self.identity.value}", self.runtime.run())

    async def on_shutdown(self) -> None:
        if self.runtime is not None:
            self.runtime.stop()
        await super().on_shutdown()
