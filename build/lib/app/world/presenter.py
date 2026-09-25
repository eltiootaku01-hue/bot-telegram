from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.world.models import WorldEventEnvelope


class WorldPresentationRejected(RuntimeError):
    """The presenter knows the event was not delivered by the transport."""


class WorldDeliveryUnknown(RuntimeError):
    """The transport result is ambiguous; manual recovery is required."""


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
        if message_id <= 0:
            raise WorldDeliveryUnknown(
                f"Presenter returned invalid message id for event #{event.event_id}"
            )
        return WorldPresentationResult(
            message_id=message_id,
            presenter_key=event.presenter.key,
        )
