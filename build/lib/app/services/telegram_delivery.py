from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram.exceptions import TelegramRetryAfter

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 3


async def with_retry_after(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> T:
    """Retry only Telegram flood-control responses using Telegram's retry_after value.

    Network/API failures are deliberately not retried here because a transport error
    can happen after Telegram accepted a request and blind replay could duplicate a
    game result or publication.
    """
    if max_retries < 0:
        raise ValueError("max_retries must not be negative")

    retries = 0
    while True:
        try:
            return await operation()
        except TelegramRetryAfter as exc:
            if retries >= max_retries:
                raise
            retries += 1
            await sleep(float(exc.retry_after))
