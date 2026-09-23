from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

from app.dialogues.models import DialogueCatalog, DialogueEvent, SUPPORTED_IDENTITIES


class DialogueStore:
    """Local JSON dialogue catalog. No network or LLM dependency."""

    def __init__(self, path: str | Path = "config/dialogues.json") -> None:
        self.path = Path(path)

    def load(self) -> DialogueCatalog:
        if not self.path.is_file():
            raise FileNotFoundError(f"Dialogue catalog not found: {self.path}")
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("Dialogue catalog root must be an object")

        normalized: dict[DialogueEvent, dict[str, tuple[str, ...]]] = {}
        for event_key, identities in raw.items():
            try:
                event = DialogueEvent(event_key)
            except ValueError as exc:
                raise ValueError(f"Unsupported dialogue event: {event_key}") from exc
            if not isinstance(identities, dict):
                raise ValueError(f"Dialogue event {event_key} must contain an object")
            per_identity: dict[str, tuple[str, ...]] = {}
            for identity_key, phrases in identities.items():
                identity = identity_key.casefold().strip()
                if identity not in SUPPORTED_IDENTITIES:
                    raise ValueError(f"Unsupported dialogue identity: {identity_key}")
                if not isinstance(phrases, list):
                    raise ValueError(f"Dialogue phrases for {event_key}/{identity} must be a list")
                if any(not isinstance(phrase, str) or not phrase.strip() for phrase in phrases):
                    raise ValueError(f"Dialogue phrases for {event_key}/{identity} must be non-empty strings")
                per_identity[identity] = tuple(phrases)
            normalized[event] = per_identity
        return DialogueCatalog(entries=normalized)

    def save(self, catalog: DialogueCatalog) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            event.value: {
                identity: list(phrases)
                for identity, phrases in sorted(by_identity.items())
            }
            for event, by_identity in sorted(catalog.entries.items(), key=lambda item: item[0].value)
        }
        encoded = json.dumps(serializable, ensure_ascii=False, indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def upsert(self, event: DialogueEvent | str, identity: str, text: str) -> None:
        catalog = self.load()
        event_key = event if isinstance(event, DialogueEvent) else DialogueEvent(event)
        identity_key = identity.casefold().strip()
        if identity_key not in SUPPORTED_IDENTITIES:
            raise ValueError(f"Unsupported dialogue identity: {identity}")
        if not text.strip():
            raise ValueError("Dialogue text cannot be empty")

        mutable = {
            event_item: {
                identity_item: list(phrases)
                for identity_item, phrases in by_identity.items()
            }
            for event_item, by_identity in catalog.entries.items()
        }
        mutable.setdefault(event_key, {}).setdefault(identity_key, []).append(text)
        self.save(
            DialogueCatalog(
                entries={
                    event_item: {
                        identity_item: tuple(phrases)
                        for identity_item, phrases in by_identity.items()
                    }
                    for event_item, by_identity in mutable.items()
                }
            )
        )

    def replace(self, event: DialogueEvent | str, identity: str, index: int, text: str) -> None:
        catalog = self.load()
        event_key = event if isinstance(event, DialogueEvent) else DialogueEvent(event)
        identity_key = identity.casefold().strip()
        phrases = list(catalog.phrases(event_key, identity_key))
        if identity_key not in SUPPORTED_IDENTITIES:
            raise ValueError(f"Unsupported dialogue identity: {identity}")
        if not phrases:
            raise ValueError(f"No dialogue entries for {event_key.value}/{identity_key}")
        if not 0 <= index < len(phrases):
            raise IndexError("Dialogue index out of range")
        if not text.strip():
            raise ValueError("Dialogue text cannot be empty")
        phrases[index] = text
        mutable = {
            event_item: {
                identity_item: list(items)
                for identity_item, items in by_identity.items()
            }
            for event_item, by_identity in catalog.entries.items()
        }
        mutable[event_key][identity_key] = phrases
        self.save(
            DialogueCatalog(
                entries={
                    event_item: {
                        identity_item: tuple(items)
                        for identity_item, items in by_identity.items()
                    }
                    for event_item, by_identity in mutable.items()
                }
            )
        )

    def remove(self, event: DialogueEvent | str, identity: str, index: int) -> None:
        catalog = self.load()
        event_key = event if isinstance(event, DialogueEvent) else DialogueEvent(event)
        identity_key = identity.casefold().strip()
        phrases = list(catalog.phrases(event_key, identity_key))
        if not 0 <= index < len(phrases):
            raise IndexError("Dialogue index out of range")
        phrases.pop(index)

        mutable = {
            event_item: {
                identity_item: list(items)
                for identity_item, items in by_identity.items()
            }
            for event_item, by_identity in catalog.entries.items()
        }
        if phrases:
            mutable[event_key][identity_key] = phrases
        else:
            mutable[event_key].pop(identity_key, None)
            if not mutable[event_key]:
                mutable.pop(event_key, None)

        self.save(
            DialogueCatalog(
                entries={
                    event_item: {
                        identity_item: tuple(items)
                        for identity_item, items in by_identity.items()
                    }
                    for event_item, by_identity in mutable.items()
                }
            )
        )

    def export(self) -> Mapping[str, Mapping[str, tuple[str, ...]]]:
        catalog = self.load()
        return {
            event.value: dict(by_identity)
            for event, by_identity in catalog.entries.items()
        }
