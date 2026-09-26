# -*- coding: utf-8 -*-

import asyncio
import random

from telegram import Update
from telegram.ext import ContextTypes


async def execute_coin_toss(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    p1_choice: str
) -> str:
    """
    Simula el lanzamiento de moneda por parte de la mesera.

    p1_choice debe ser 'CARA' o 'CRUZ'.
    La función anima el lanzamiento en el mensaje de callback y devuelve
    el resultado final ('CARA' o 'CRUZ').
    """
    query = update.callback_query
    if query is None:
        raise ValueError("execute_coin_toss requiere un callback_query activo.")

    p1_choice = p1_choice.upper()
    if p1_choice not in {"CARA", "CRUZ"}:
        raise ValueError("p1_choice debe ser 'CARA' o 'CRUZ'.")

    # Evita dejar el callback de Telegram pendiente durante la animación.
    await query.answer()

    coin_frames = [
        "🪙 *La mesera lanza la moneda al aire...* [ ⠋ ]",
        "🪙 *La moneda gira en el aire...* [ ⠙ ]",
        "🪙 *La moneda cae sobre la mesa...* [ ⠹ ]",
    ]

    for frame in coin_frames:
        await query.edit_message_text(text=frame, parse_mode="Markdown")
        await asyncio.sleep(0.5)

    result = random.choice(["CARA", "CRUZ"])
    p1_won = p1_choice == result

    winner_text = (
        "¡El Retador gana el tiro!"
        if p1_won
        else "¡El Desafiado gana el tiro!"
    )

    final_message = (
        "🪙 **¡Resultado del Lanzamiento!**\n\n"
        f"La moneda cayó en: **{result}**\n"
        f"✨ {winner_text} Elige quién toma el primer turno."
    )

    await query.edit_message_text(text=final_message, parse_mode="Markdown")
    return result
