from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router(name="core-errors")


@router.error()
async def handle_unexpected_update_error(event: ErrorEvent) -> bool:
    """Keep one broken update from escaping into the polling loop."""
    logger.exception(
        "Unhandled Telegram update error: %s",
        event.exception,
        exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
    )
    return True
