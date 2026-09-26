# -*- coding: utf-8 -*-
import logging

from telegram.ext import ContextTypes


logger = logging.getLogger(__name__)


# Mensaje característico al agotarse el tiempo.
WAITRESS_EXIT_TEXT = (
    "Uhhh... me gustaría seguir hablando, pero el jefe me está mirando "
    "y no puedo holgazanear otra vez... ¡Cuídate! 😉✨"
)


async def auto_delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina un mensaje del chat cuando expira su temporizador de ruido."""
    job_data = context.job.data or {}
    chat_id = job_data.get("chat_id")
    message_id = job_data.get("message_id")

    if chat_id is None or message_id is None:
        logger.warning("Job de auto-borrado sin chat_id o message_id.")
        return

    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )
    except Exception as exc:
        logger.warning(
            "No se pudo eliminar el mensaje %s en %s: %s",
            message_id,
            chat_id,
            exc,
        )


async def waitress_timeout_exit_job(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Envía la despedida de la mesera tras un período de inactividad."""
    job_data = context.job.data or {}
    chat_id = job_data.get("chat_id")

    if chat_id is None:
        logger.warning("Job de inactividad de mesera sin chat_id.")
        return

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=WAITRESS_EXIT_TEXT,
        )
    except Exception as exc:
        logger.warning(
            "No se pudo enviar la despedida de la mesera en %s: %s",
            chat_id,
            exc,
        )


def schedule_message_auto_delete(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    delay_seconds: int = 20,
) -> None:
    """Programa el borrado automático de mensajes considerados ruido."""
    if context.job_queue:
        context.job_queue.run_once(
            auto_delete_message_job,
            when=delay_seconds,
            data={"chat_id": chat_id, "message_id": message_id},
            name=f"delete_{chat_id}_{message_id}",
        )


def start_waitress_inactivity_timer(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    delay_seconds: int = 30,
) -> None:
    """Inicia o reinicia el temporizador de inactividad de la mesera."""
    stop_waitress_inactivity_timer(context, chat_id)

    if context.job_queue:
        context.job_queue.run_once(
            waitress_timeout_exit_job,
            when=delay_seconds,
            data={"chat_id": chat_id},
            name=f"waitress_timer_{chat_id}",
        )


def stop_waitress_inactivity_timer(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """Cancela el temporizador si el usuario responde a tiempo."""
    if context.job_queue:
        current_jobs = context.job_queue.get_jobs_by_name(
            f"waitress_timer_{chat_id}"
        )
        for job in current_jobs:
            job.schedule_removal()
