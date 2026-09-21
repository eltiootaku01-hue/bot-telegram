from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Protocol

from aiogram.exceptions import TelegramBadRequest


WAITING_MESSAGES: tuple[str, ...] = (
    "Mmm... dame un segundo ⏳",
    "Un minuto más, lo prometo...",
    "¡Lo tengo! ✨",
)


@dataclass(frozen=True, slots=True)
class ProcessingResultDTO:
    """Small Telegram-facing DTO returned by long-running Core operations."""

    text: str
    reply_markup: Any | None = None


class _MessageLike(Protocol):
    async def answer(self, text: str, **kwargs: Any) -> Any: ...


class _TransientMessageLike(Protocol):
    async def edit_text(self, text: str, **kwargs: Any) -> Any: ...
    async def delete(self) -> Any: ...


class ProcessingFeedback:
    """Own one transient message and replace it with the final result."""

    def __init__(
        self,
        target: _MessageLike,
        *,
        chooser: callable | None = None,
    ) -> None:
        self._target = target
        self._chooser = chooser or secrets.choice
        self._transient: _TransientMessageLike | None = None
        self._completed = False

    async def start(self) -> None:
        if self._transient is not None:
            return
        text = self._chooser(WAITING_MESSAGES)
        self._transient = await self._target.answer(text)

    async def finish(self, result: ProcessingResultDTO | str) -> None:
        if isinstance(result, str):
            result = ProcessingResultDTO(text=result)
        if self._transient is None:
            await self._target.answer(result.text, reply_markup=result.reply_markup)
            self._completed = True
            return

        try:
            await self._transient.edit_text(
                result.text,
                reply_markup=result.reply_markup,
            )
        except TelegramBadRequest:
            # Telegram does not offer a cross-type atomic edit. A text result
            # should normally take the single-request edit path; this fallback
            # keeps the user-facing contract recoverable when the edit is rejected.
            try:
                await self._transient.delete()
            finally:
                await self._target.answer(
                    result.text,
                    reply_markup=result.reply_markup,
                )
        self._completed = True

    async def cleanup(self) -> None:
        if self._completed or self._transient is None:
            return
        try:
            await self._transient.delete()
        except Exception:
            pass
        finally:
            self._transient = None

    async def __aenter__(self) -> "ProcessingFeedback":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.cleanup()
