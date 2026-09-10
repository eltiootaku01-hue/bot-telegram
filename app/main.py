import asyncio
import logging

from aiogram import Dispatcher

from app.core.bot import build_dispatcher
from app.core.config import get_settings
from app.core.logging import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    bot, dispatcher = build_dispatcher(settings)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.getLogger(__name__).info("Starting community bot")
    asyncio.run(run())
