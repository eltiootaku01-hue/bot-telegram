from __future__ import annotations

from typing import Protocol


class NotificationSink(Protocol):
    """Contract implemented by platform-specific notification adapters."""

    async def start(self) -> None:
        """Start the sink's client/session and background workers."""
        ...

    async def stop(self, drain_timeout: float = 10.0) -> None:
        """Stop the sink, draining queued work up to the supplied timeout."""
        ...

    async def enqueue_notification(
        self,
        event_id: str,
        destination_id: int,
        title: str,
        url: str,
        author: str,
    ) -> None:
        """Queue one event for delivery to the sink's mapped destination."""
        ...
