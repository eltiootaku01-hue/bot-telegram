"""Sunna: the reserved WaifuMon game identity."""

from app.core.bot import build_dispatcher
from app.core.config import get_settings


async def run() -> None:
    bot, dispatcher, database = build_dispatcher(get_settings())
    await database.create_schema()
    try:
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
