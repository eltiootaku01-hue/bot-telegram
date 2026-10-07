# -*- coding: utf-8 -*-
"""Frozen CAFE-01 domain foundation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RelationshipStatus(str, Enum):
    """Minimal closed relationship vocabulary."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class CafeDomainEventType(str, Enum):
    """Minimal closed event vocabulary for the frozen foundation."""

    CHARACTER_STATE_CHANGED = "character_state_changed"
    RELATIONSHIP_STATE_CHANGED = "relationship_state_changed"


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _require_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    return value


def _require_positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return value


@dataclass(frozen=True, slots=True)
class CafeDomainIdentity:
    """Stable identity inside the Cafe domain.

    actor_keys are opaque references to existing platform Actors. This class
    never authenticates, authorizes, parses credentials, or links platforms.
    """

    identity_id: str
    actor_keys: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.identity_id, "identity_id")
        if not isinstance(self.actor_keys, tuple):
            raise TypeError("actor_keys must be an immutable tuple")
        if not self.actor_keys:
            raise ValueError("actor_keys must not be empty")

        normalized = tuple(
            _require_text(actor_key, "actor_keys item")
            for actor_key in self.actor_keys
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError("actor_keys must not contain duplicates")

        object.__setattr__(self, "actor_keys", normalized)
        _require_datetime(self.created_at, "created_at")
        _require_datetime(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class CharacterRef:
    """Stable reference to an existing Character V1 by character_id only."""

    character_id: str

    def __post_init__(self) -> None:
        _require_text(self.character_id, "character_id")


@dataclass(frozen=True, slots=True)
class CharacterState:
    """Immutable representation of dynamic Cafe-domain Character state."""

    character_ref: CharacterRef
    evolution_stage_id: str | None
    state_version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.character_ref, CharacterRef):
            raise TypeError("character_ref must be a CharacterRef")

        if self.evolution_stage_id is not None:
            _require_text(self.evolution_stage_id, "evolution_stage_id")

        _require_positive_int(self.state_version, "state_version")
        _require_datetime(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class RelationshipState:
    """Dynamic Cafe-domain identity-to-character relationship state."""

    domain_identity_id: str
    character_ref: CharacterRef
    status: RelationshipStatus
    started_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.domain_identity_id, "domain_identity_id")
        if not isinstance(self.character_ref, CharacterRef):
            raise TypeError("character_ref must be a CharacterRef")
        if not isinstance(self.status, RelationshipStatus):
            raise TypeError("status must be a RelationshipStatus")
        _require_datetime(self.started_at, "started_at")
        _require_datetime(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class CafeDomainEvent:
    """Immutable Cafe-domain event contract with no runtime behavior."""

    event_id: str
    event_type: CafeDomainEventType
    occurred_at: datetime
    domain_identity_id: str | None
    character_ref: CharacterRef | None
    correlation_id: str | None

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        if not isinstance(self.event_type, CafeDomainEventType):
            raise TypeError("event_type must be a CafeDomainEventType")
        _require_datetime(self.occurred_at, "occurred_at")

        if self.domain_identity_id is not None:
            _require_text(self.domain_identity_id, "domain_identity_id")

        if self.character_ref is not None and not isinstance(
            self.character_ref,
            CharacterRef,
        ):
            raise TypeError("character_ref must be a CharacterRef or None")

        if self.correlation_id is not None:
            _require_text(self.correlation_id, "correlation_id")


__all__ = [
    "CafeDomainEvent",
    "CafeDomainEventType",
    "CafeDomainIdentity",
    "CharacterRef",
    "CharacterState",
    "RelationshipState",
    "RelationshipStatus",
]
