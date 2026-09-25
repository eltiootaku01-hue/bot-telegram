from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OperationMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


@dataclass(frozen=True, slots=True)
class CafeTable:
    key: str
    label: str
    chat_id: int
    message_thread_id: int
    zone_key: str = "lounge"
    x: int = 0
    y: int = 0


@dataclass(frozen=True, slots=True)
class BotAvatar:
    identity: str
    label: str
    x: int
    y: int
    table_key: str | None
    mode: OperationMode
    status: str


@dataclass(frozen=True, slots=True)
class MoveCommand:
    identity: str
    table: CafeTable


@dataclass(frozen=True, slots=True)
class ManualMessageCommand:
    identity: str
    chat_id: int
    message_thread_id: int | None
    text: str
    protect_content: bool = False


@dataclass(frozen=True, slots=True)
class TemporaryMessagePolicy:
    minimum_seconds: float = 3.0
    maximum_seconds: float = 20.0
    characters_per_second: int = 25

    def delay_for(self, text: str) -> float:
        seconds = max(self.minimum_seconds, len(text) / self.characters_per_second)
        return min(self.maximum_seconds, seconds)
