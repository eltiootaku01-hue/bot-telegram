# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.decorators.clean_decorators import auto_clean


@auto_clean(
    delay_seconds=20,
    clean_user_command=True,
    clean_bot_response=True,
)
async def inventory_command_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Muestra el inventario rápido y limpia comando/respuesta tras 20 segundos."""
    if update.message is None:
        return None

    return await update.message.reply_text(
        "🧰 **Tu Baúl (Telegram):**\n"
        "- 1x Carta Waifu Rara\n"
        "- 200 Monedas\n\n"
        "_(Este mensaje se borrará en 20s)_",
        parse_mode="Markdown",
    )


@auto_clean(delay_seconds=15)
async def roll_dice_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Tirada de dados para combate/eventos; se limpia tras 15 segundos."""
    if update.message is None:
        return None

    return await update.message.reply_text(
        "🎲 Has sacado un **6** en tu tirada de iniciativa.",
        parse_mode="Markdown",
    )
