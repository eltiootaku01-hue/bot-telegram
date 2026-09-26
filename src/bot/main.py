# -*- coding: utf-8 -*-
import logging
from telegram.ext import ApplicationBuilder

from src.bot.handlers.drop_handler import register_drop_handlers
from src.bot.handlers.match_handler import register_match_handlers
from src.core.config import settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def create_bot_app():
    """
    Inicializa la aplicación python-telegram-bot y registra todos los routers/handlers.
    """
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Registrar el módulo de drops (comando /drop y callbacks claim_drop:)
    register_drop_handlers(app)

    # Registrar el módulo de duelos (comando /duelo y callbacks accept/decline)
    register_match_handlers(app)

    return app


if __name__ == "__main__":
    application = create_bot_app()
    application.run_polling()
