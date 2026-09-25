from __future__ import annotations

import logging
from typing import Any

from src.db.event_repository import EventRepository
from src.service.notification_dispatcher import TelegramNotificationDispatcher

logger = logging.getLogger("EventRecovery")


async def recover_orphan_events(
    repo: EventRepository,
    dispatcher: TelegramNotificationDispatcher,
) -> int:
    """Re-queue QUEUED/RETRYING events whose delivery was interrupted."""
    pending_events: list[dict[str, Any]] = await repo.get_pending_events()
    if not pending_events:
        logger.info("No hay eventos huérfanos pendientes de despacho.")
        return 0

    logger.warning(
        "Iniciando recuperación de %d eventos pendientes...",
        len(pending_events),
    )
    recovered_count = 0

    for event in pending_events:
        event_id = str(event["event_id"])
        bot_name = str(event["bot_name"])

        if bot_name.strip().casefold() not in dispatcher.bots:
            logger.error(
                "No se pudo re-encolar el evento %s: el bot '%s' "
                "ya no está configurado.",
                event_id,
                bot_name,
            )
            continue

        try:
            await dispatcher.enqueue_notification(
                event_id=event_id,
                bot_name=bot_name,
                thread_id=int(event["thread_id"]),
                title=str(event["title"]),
                url=str(event["url"]),
                author=str(event["author"]),
            )
            recovered_count += 1
        except Exception:
            logger.exception(
                "Error re-encolando evento huérfano %s.",
                event_id,
            )

    logger.info(
        "Recuperación completada: %d/%d re-encolados.",
        recovered_count,
        len(pending_events),
    )
    return recovered_count
