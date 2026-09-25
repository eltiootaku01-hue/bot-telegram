import asyncio
import logging

from app.core.bot import build_dispatcher
from app.core.config import get_settings
from app.core.logging import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    identity = settings.bot_identity
    bot, dispatcher, database = build_dispatcher(settings, identity)
    await database.create_schema()

    try:
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    logging.getLogger(__name__).info("Starting %s community bot", get_settings().bot_identity.value)
    asyncio.run(run())
