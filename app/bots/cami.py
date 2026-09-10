"""Cami: analytics, diagnostics and operational intelligence identity."""

import asyncio

from app.core.bot import build_dispatcher
from app.core.config import get_settings
from app.core.identity import BotIdentity


async def run() -> None:
    bot, dispatcher, database = build_dispatcher(get_settings(), BotIdentity.CAMI)
    await database.create_schema()
    try:
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
