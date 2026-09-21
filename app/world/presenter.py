from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.world.models import WorldEventEnvelope


class WorldMessageTransport(Protocol):
    async def send(self, presenter_key: str, chat_id: int, text: str) -> int:
        """Send one world presentation and return Telegram message id."""


@dataclass(frozen=True, slots=True)
class WorldPresentationResult:
    message_id: int
    presenter_key: str


class WorldPresenter:
    """Presenter adapter; the world domain knows nothing about Telegram identities."""

    def __init__(self, send: Callable[[str, int, str], Awaitable[int]]) -> None:
        self._send = send

    async def present(self, event: WorldEventEnvelope) -> WorldPresentationResult:
        message_id = await self._send(
            event.presenter.key,
            event.chat_id,
            event.render_text(),
        )
        return WorldPresentationResult(
            message_id=message_id,
            presenter_key=event.presenter.key,
        )
