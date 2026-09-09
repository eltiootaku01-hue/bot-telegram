"""Contratos serializables de agentes, diseñados para expedientes ya filtrados."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from bot_ia.context import ContextPack
from bot_ia.contracts import Confidence, SessionState
from bot_ia.librarian.models import EvidencePack, SpoilerScope

from .output_contract import IAChanOutputContract


class AgentStatus(str, Enum):
    COMPLETE = "complete"
    REJECTED = "rejected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class ExternalReference:
    source: str
    medium: str
    version: str
    published_on: date | None
    confidence: Confidence
    spoiler: SpoilerScope
    applicability: str


@dataclass(frozen=True, slots=True)
class AgentRequest:
    agent_id: str
    universe_id: str
    intent: str
    user_request: str
    state: SessionState | None
    context_pack: ContextPack
    evidence_pack: EvidencePack
    constraints: tuple[str, ...] = ()
    external_references: tuple[ExternalReference, ...] = ()

    def __post_init__(self) -> None:
        if not self.agent_id or not self.universe_id or not self.user_request:
            raise ValueError("agent_id, universe_id and user_request are required")

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


@dataclass(frozen=True, slots=True)
class AgentFinding:
    category: str
    value: str
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentResult:
    agent_id: str
    status: AgentStatus
    answer: str
    findings: tuple[AgentFinding, ...]
    evidence_source_ids: tuple[str, ...]
    uncertainty: str | None
    conflicts: tuple[str, ...]
    recommendation: str
    output_contract: IAChanOutputContract | None = None

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {item.name: _primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    return value
