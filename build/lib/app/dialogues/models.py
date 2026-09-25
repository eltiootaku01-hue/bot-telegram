from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DialogueEvent(StrEnum):
    ON_CAMPANA_RUNG = "ON_CAMPANA_RUNG"
    ON_CARD_ROLL = "ON_CARD_ROLL"
    ON_WAIFU_ENCOUNTER = "ON_WAIFU_ENCOUNTER"
    ON_WAIFU_POKER = "ON_WAIFU_POKER"
    ON_WELCOME = "ON_WELCOME"
    ON_COOLDOWN = "ON_COOLDOWN"


SUPPORTED_IDENTITIES = frozenset({"cari", "sunna", "cami", "chie"})


@dataclass(frozen=True, slots=True)
class DialogueEntry:
    event: DialogueEvent
    identity: str
    text: str

    def __post_init__(self) -> None:
        identity = self.identity.casefold().strip()
        if identity not in SUPPORTED_IDENTITIES:
            raise ValueError(f"Unsupported dialogue identity: {self.identity}")
        if not self.text.strip():
            raise ValueError("Dialogue text cannot be empty")
        object.__setattr__(self, "identity", identity)


@dataclass(frozen=True, slots=True)
class DialogueCatalog:
    entries: dict[DialogueEvent, dict[str, tuple[str, ...]]]

    def __post_init__(self) -> None:
        for event, by_identity in self.entries.items():
            if not isinstance(event, DialogueEvent):
                raise ValueError("Dialogue catalog contains an unsupported event")
            for identity, phrases in by_identity.items():
                if identity not in SUPPORTED_IDENTITIES:
                    raise ValueError(f"Unsupported dialogue identity: {identity}")
                if not phrases:
                    raise ValueError(f"Dialogue event {event.value} has no phrases for {identity}")
                if any(not phrase.strip() for phrase in phrases):
                    raise ValueError(f"Dialogue event {event.value} has an empty phrase")

    def phrases(self, event: DialogueEvent | str, identity: str) -> tuple[str, ...]:
        event_key = event if isinstance(event, DialogueEvent) else DialogueEvent(event)
        identity_key = identity.casefold().strip()
        return self.entries.get(event_key, {}).get(identity_key, ())
