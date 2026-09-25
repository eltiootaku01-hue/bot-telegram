"""WorldBot: optional neutral presenter for persistent Game World events.

WorldBot is intentionally not a BotIdentity and does not own game rules.
It only transports events already created and persisted by the independent World Core.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.database import Database
from app.modules.world.module import WorldCatalogModule
from app.modules.world.presenter import WorldPresentationModule
from app.world.models import PresenterKind, WorldPresenterRef

logger = logging.getLogger(__name__)

WORLD_BOT_PRESENTER = WorldPresenterRef(
    key="world",
    kind=PresenterKind.WORLD_BOT,
)


def build_world_bot(settings: Settings) -> tuple[Bot, Database, WorldCatalogModule, WorldPresentationModule]:
    """Build only the transport-side components required by the WorldBot."""
    token = settings.bot_token_world.strip()
    if not token:
        raise ValueError(
            "No WorldBot token configured. Set BOT_TOKEN_WORLD in .env before starting app.bots.world."
        )

    bot = Bot(token=token)
    database = Database(settings.database_url)
    catalog = WorldCatalogModule(database)
    presenter = WorldPresentationModule(
        database,
        settings=settings,
        presenter=WORLD_BOT_PRESENTER,
    )
    return bot, database, catalog, presenter


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    bot, database, catalog, presenter = build_world_bot(settings)

    try:
        await database.create_schema()
        bot_info = await bot.get_me()
        logger.info(
            "WorldBot authenticated: id=%s username=@%s",
            bot_info.id,
            bot_info.username or "-",
        )
        await catalog.on_startup(bot)
        await presenter.on_startup(bot)
        logger.info("WorldBot started as presenter=%s", WORLD_BOT_PRESENTER.key)
        stop = asyncio.Event()
        await stop.wait()
    finally:
        await presenter.on_shutdown()
        await catalog.on_shutdown()
        await database.close()
        await bot.session.close()
        logger.info("WorldBot stopped")


if __name__ == "__main__":
    asyncio.run(run())
