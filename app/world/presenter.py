from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.world.models import WorldEventEnvelope


class WorldMessageTransport(Protocol):
    async def send(self, event: WorldEventEnvelope) -> int:
        """Present one world event and return the Telegram message id."""


@dataclass(frozen=True, slots=True)
class WorldPresentationResult:
    message_id: int
    presenter_key: str


class WorldPresenter:
    """Presenter adapter; the world domain knows nothing about Telegram identities."""

    def __init__(self, send: Callable[[WorldEventEnvelope], Awaitable[int]]) -> None:
        self._send = send

    async def present(self, event: WorldEventEnvelope) -> WorldPresentationResult:
        message_id = await self._send(event)
        return WorldPresentationResult(
            message_id=message_id,
            presenter_key=event.presenter.key,
        )
