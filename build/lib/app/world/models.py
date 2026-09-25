from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class WorldEventType(StrEnum):
    GAME_NEWS = "game_news"
    REWARD_NOTICE = "reward_notice"
    WAIFU_ARRIVAL = "waifu_arrival"
    MYSTERY_CLUE = "mystery_clue"


class WorldEventStatus(StrEnum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    DELIVERY_UNKNOWN = "delivery_unknown"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PresenterKind(StrEnum):
    EXISTING_BOT = "existing_bot"
    WORLD_BOT = "world_bot"


@dataclass(frozen=True, slots=True)
class WorldPresenterRef:
    """Transport identity used only to present a world event."""

    key: str
    kind: PresenterKind

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("presenter key must not be empty")


@dataclass(frozen=True, slots=True)
class WorldEventEnvelope:
    """Immutable event view passed from world storage to a presenter adapter."""

    event_id: int
    event_key: str
    event_type: WorldEventType
    chat_id: int
    presenter: WorldPresenterRef
    title: str
    payload: Mapping[str, object]
    status: WorldEventStatus
    lock_time: datetime

    def render_text(self) -> str:
        body = self.payload.get("text")
        if body is None:
            body = self.payload.get("message")
        if body is None:
            body = ""
        text = str(body).strip()
        if not text:
            return self.title
        if not self.title.strip():
            return text
        return f"{self.title.strip()}\n\n{text}"
