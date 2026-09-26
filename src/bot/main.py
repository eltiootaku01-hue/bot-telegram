# -*- coding: utf-8 -*-
import logging

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from src.bot.handlers.battle_handler import register_battle_handlers
from src.bot.handlers.deck_selection_handler import (
    deck_callback_handler,
    start_deck_selection_handler,
)
from src.bot.handlers.drop_handler import register_drop_handlers
from src.bot.handlers.match_handler import register_match_handlers
from src.core.config import settings


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def create_bot_app():
    """
    Inicializa la aplicación python-telegram-bot y registra todos los handlers.
    """
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Registrar el módulo de drops.
    register_drop_handlers(app)

    # Registrar el módulo de duelos.
    register_match_handlers(app)

    # Registrar el motor de combate.
    register_battle_handlers(app)

    # Selector interactivo de mazo.
    app.add_handler(CommandHandler("mazo", start_deck_selection_handler))
    app.add_handler(
        CallbackQueryHandler(
            deck_callback_handler,
            pattern=r"^deck_",
        )
    )

    return app


if __name__ == "__main__":
    application = create_bot_app()
    application.run_polling()
