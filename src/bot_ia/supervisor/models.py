# -*- coding: utf-8 -*-
"""Modelos mínimos del Observation Core del Supervisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class Confidence(str, Enum):
    VERIFIED = "VERIFIED"
    INSPECTED = "INSPECTED"
    INFERRED = "INFERRED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    TESTED = "TESTED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class EvidenceType(str, Enum):
    FILE_EVIDENCE = "FILE_EVIDENCE"
    GIT_EVIDENCE = "GIT_EVIDENCE"
    TEST_EVIDENCE = "TEST_EVIDENCE"
    RUNTIME_EVIDENCE = "RUNTIME_EVIDENCE"
    USER_PROVIDED_EVIDENCE = "USER_PROVIDED_EVIDENCE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(slots=True)
class Observation:
    observation_id: str
    task_id: str | None
    source: str
    target: str
    observation_type: str
    value: Any
    timestamp: str
    scope: str
    status: EvidenceStatus
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        source: str,
        target: str,
        observation_type: str,
        value: Any,
        scope: str,
        task_id: str | None = None,
        status: EvidenceStatus = EvidenceStatus.OBSERVED,
        metadata: dict[str, Any] | None = None,
    ) -> "Observation":
        return cls(
            observation_id=new_id("obs"),
            task_id=task_id,
            source=source,
            target=target,
            observation_type=observation_type,
            value=value,
            timestamp=utc_now(),
            scope=scope,
            status=status,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(slots=True)
class Evidence:
    evidence_id: str
    type: EvidenceType
    source: str
    timestamp: str
    scope: str
    result: EvidenceStatus
    command: list[str] | None = None
    exit_code: int | None = None
    artifact: str | None = None
    hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: Confidence = Confidence.INSPECTED

    @classmethod
    def create(
        cls,
        *,
        evidence_type: EvidenceType,
        source: str,
        scope: str,
        result: EvidenceStatus,
        command: list[str] | None = None,
        exit_code: int | None = None,
        artifact: str | None = None,
        hash_value: str | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Confidence = Confidence.INSPECTED,
    ) -> "Evidence":
        return cls(
            evidence_id=new_id("ev"),
            type=evidence_type,
            source=source,
            timestamp=utc_now(),
            scope=scope,
            result=result,
            command=list(command) if command else None,
            exit_code=exit_code,
            artifact=artifact,
            hash=hash_value,
            metadata=dict(metadata or {}),
            confidence=confidence,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        data["result"] = self.result.value
        data["confidence"] = self.confidence.value
        return data


@dataclass(slots=True)
class AuditEvent:
    audit_id: str
    task_id: str | None
    operation: str
    actor: str
    timestamp: str
    result: str
    evidence_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        operation: str,
        actor: str,
        result: str,
        task_id: str | None = None,
        evidence_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AuditEvent":
        return cls(
            audit_id=new_id("audit"),
            task_id=task_id,
            operation=operation,
            actor=actor,
            timestamp=utc_now(),
            result=result,
            evidence_id=evidence_id,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
