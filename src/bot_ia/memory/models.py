"""Contratos de memoria persistente; la memoria nunca es canon."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from bot_ia.contracts import Confidence


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    WORK_DECISION = "work_decision"
    OPERATIONAL = "operational"
    NARRATIVE_CONTEXT = "narrative_context"
    NOTE = "note"
    TEMPORARY = "temporary"
    PERSISTENT = "persistent"


class MemoryStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CONFLICT = "conflict"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class PersistentMemoryRecord:
    memory_id: str
    universe_id: str
    user_id: str
    conversation_id: str | None
    memory_type: MemoryType
    content: str
    source: str
    created_at: datetime
    updated_at: datetime
    approved_by_author: bool
    status: MemoryStatus
    confidence: Confidence
    expires_at: datetime | None
    revoked_at: datetime | None
    tags: tuple[str, ...]
    related_entities: tuple[str, ...]
    provenance: str
    supersedes: str | None = None
    conflicts_with: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.memory_id or not self.universe_id or not self.user_id or not self.content.strip() or not self.source or not self.provenance:
            raise ValueError("persistent memory requires identifiers, content, source and provenance")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("memory timestamps must be timezone-aware")
        if self.expires_at and self.expires_at <= self.created_at:
            raise ValueError("memory expiry must be after creation")
        if self.status is MemoryStatus.ACTIVE and not self.approved_by_author:
            raise ValueError("active memory requires explicit authorization")

    def to_dict(self) -> dict[str, object]:
        return {"memory_id": self.memory_id, "universe_id": self.universe_id, "user_id": self.user_id, "conversation_id": self.conversation_id, "type": self.memory_type.value, "content": self.content, "source": self.source, "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat(), "approved_by_author": self.approved_by_author, "status": self.status.value, "confidence": self.confidence.value, "expires_at": self.expires_at.isoformat() if self.expires_at else None, "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None, "tags": self.tags, "related_entities": self.related_entities, "provenance": self.provenance, "supersedes": self.supersedes, "conflicts_with": self.conflicts_with}


@dataclass(frozen=True, slots=True)
class MemoryMatch:
    record: PersistentMemoryRecord
    relevance: float
