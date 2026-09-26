# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.services.chat_cleanup_service import (
    schedule_message_auto_delete,
    start_waitress_inactivity_timer,
    stop_waitress_inactivity_timer,
)


async def handle_missing_cards_support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Responde cuando un usuario pregunta por sus cartas de Discord en Telegram.

    La explicación permanece visible en el grupo para que pueda servir de
    referencia a otros usuarios. Solo el mensaje de entrada ruidoso se
    programa para borrado.
    """
    if update.effective_chat is None or update.message is None:
        return

    chat_id = update.effective_chat.id
    user_message_id = update.message.message_id

    # El mensaje de entrada puede eliminarse como ruido sin borrar la
    # explicación que queda visible para el grupo.
    schedule_message_auto_delete(
        context,
        chat_id=chat_id,
        message_id=user_message_id,
        delay_seconds=15,
    )

    response_text = (
        "Espere, busco... 📋

"
        "Perdón, pero usted nunca consiguió esa carta en este grupo de Telegram. "
        "¡Los baúles de Discord y Telegram son completamente independientes "
        "para evitar confusiones! Sus cartas siguen a salvo en Discord.

"
        "¿Eso era todo? Cami me está llamando..."
    )

    await update.message.reply_text(response_text)

    # La explicación queda visible; solo se controla la inactividad de la
    # conversación durante los siguientes 30 segundos.
    start_waitress_inactivity_timer(
        context,
        chat_id=chat_id,
        delay_seconds=30,
    )


async def handle_user_followup_response(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Cancela el retiro de la mesera cuando el usuario continúa la charla."""
    if update.effective_chat is None:
        return

    chat_id = update.effective_chat.id
    stop_waitress_inactivity_timer(context, chat_id)

    # El procesamiento específico de la respuesta puede continuar aquí.
