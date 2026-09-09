"""Modelos de dominio de Fase 1C; no realizan E/S ni llamadas de red."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re

_UNIVERSE_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class AuthorityLevel(str, Enum):
    PRIMARY = "primary"
    INTERNAL_CANON = "internal_canon"
    AUTHORIAL_DECISION = "authorial_decision"
    PLAN = "plan"
    EXTERNAL_REFERENCE = "external_reference"
    UNKNOWN = "unknown"


class SourceStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class CanonStatus(str, Enum):
    CANON = "canon"
    NON_CANON = "non_canon"
    PLANNING = "planning"
    EXTERNAL = "external"
    UNKNOWN = "unknown"
    CONFLICTED = "conflicted"


class EvidenceStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    AMBIGUOUS = "ambiguous"
    UNVERIFIED = "unverified"


class EpistemicStatus(str, Enum):
    ESTABLISHED = "established"
    NOT_ESTABLISHED = "not_established"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    AMBIGUOUS = "ambiguous"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


def _validate_universe_id(universe_id: str) -> None:
    if not _UNIVERSE_ID.fullmatch(universe_id):
        raise ValueError("universe_id must be lowercase snake_case (2-64 characters)")


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: str
    universe_id: str
    source_type: str
    authority: AuthorityLevel
    status: SourceStatus
    path: Path
    content_hash: str
    canon_status: CanonStatus = CanonStatus.UNKNOWN
    provenance: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        _validate_universe_id(self.universe_id)
        if not self.source_id or not self.source_type or not self.content_hash:
            raise ValueError("source_id, source_type and content_hash are required")
        if not self.path:
            raise ValueError("path is required")


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    universe_id: str
    content: str
    authorized: bool
    scope: str
    provenance: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_universe_id(self.universe_id)
        if not self.memory_id or not self.content or not self.scope or not self.provenance:
            raise ValueError("memory fields cannot be empty")
        if self.expires_at and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")

    def usable_at(self, now: datetime) -> bool:
        return self.authorized and (self.expires_at is None or now < self.expires_at)


@dataclass(slots=True)
class SessionState:
    session_id: str
    universe_id: str
    expires_at: datetime
    active_entity_ids: tuple[str, ...] = ()
    recent_reference_ids: tuple[str, ...] = ()
    chapter_id: str | None = None
    mode: str = "default"

    def __post_init__(self) -> None:
        _validate_universe_id(self.universe_id)
        if not self.session_id:
            raise ValueError("session_id is required")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if not self.mode:
            raise ValueError("mode is required")

    def is_expired(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return now >= self.expires_at


@dataclass(frozen=True, slots=True)
class UniverseDefinition:
    universe_id: str
    display_name: str
    root_path: Path
    spoiler_policy: str = "strict"
    language: str = "es"

    def __post_init__(self) -> None:
        _validate_universe_id(self.universe_id)
        if not self.display_name:
            raise ValueError("display_name is required")
        if not self.root_path:
            raise ValueError("root_path is required")
