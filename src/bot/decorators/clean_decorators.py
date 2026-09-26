# -*- coding: utf-8 -*-
import functools
import logging
from typing import Any, Callable

from telegram import Message, Update
from telegram.ext import ContextTypes

from src.bot.services.chat_cleanup_service import schedule_message_auto_delete


logger = logging.getLogger(__name__)


def auto_clean(
    delay_seconds: int = 20,
    clean_user_command: bool = True,
    clean_bot_response: bool = True,
) -> Callable:
    """
    Programa la limpieza automática de comandos y respuestas de un handler.

    Para que la respuesta del bot pueda limpiarse, el handler decorado debe
    devolver el objeto Message generado por reply_text() (o una lista de
    objetos Message).
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            chat_id = (
                update.effective_chat.id
                if update.effective_chat is not None
                else None
            )

            # 1. Limpiar el comando/mensaje del usuario.
            if (
                clean_user_command
                and update.effective_message is not None
                and chat_id is not None
            ):
                schedule_message_auto_delete(
                    context=context,
                    chat_id=chat_id,
                    message_id=update.effective_message.message_id,
                    delay_seconds=delay_seconds,
                )

            # 2. Ejecutar la lógica principal.
            result = await func(update, context, *args, **kwargs)

            # 3. Limpiar las respuestas devueltas por el handler.
            if clean_bot_response and result and chat_id is not None:
                messages = (
                    [result]
                    if isinstance(result, Message)
                    else result
                    if isinstance(result, list)
                    else []
                )

                for message in messages:
                    if isinstance(message, Message):
                        schedule_message_auto_delete(
                            context=context,
                            chat_id=chat_id,
                            message_id=message.message_id,
                            delay_seconds=delay_seconds,
                        )

            return result

        return wrapper

    return decorator
