# -*- coding: utf-8 -*-
"""Contratos puros de hipótesis, reparación y verificación del Supervisor.

Este módulo registra intención y resultados. No ejecuta escrituras, no modifica
ScopeLock, no persiste por sí mismo y no sustituye Authorization ni Execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from .authorization import (
    AuthorizationCheckResult,
    WriteAuthorization,
    check_authorization,
)
from .models import AuditEvent, Confidence, new_id, utc_now
from .scope import ScopeLock, ScopeOperation
from .task_contract import Task


class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"


class RepairStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    BLOCKED = "BLOCKED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


class RepairAttemptStatus(str, Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ABORTED = "ABORTED"


_HYPOTHESIS_TRANSITIONS = {
    HypothesisStatus.PROPOSED: frozenset(
        {HypothesisStatus.TESTING, HypothesisStatus.BLOCKED, HypothesisStatus.CLOSED}
    ),
    HypothesisStatus.TESTING: frozenset(
        {
            HypothesisStatus.SUPPORTED,
            HypothesisStatus.REFUTED,
            HypothesisStatus.INCONCLUSIVE,
            HypothesisStatus.BLOCKED,
            HypothesisStatus.CLOSED,
        }
    ),
    HypothesisStatus.SUPPORTED: frozenset({HypothesisStatus.CLOSED}),
    HypothesisStatus.REFUTED: frozenset({HypothesisStatus.CLOSED}),
    HypothesisStatus.INCONCLUSIVE: frozenset(
        {HypothesisStatus.TESTING, HypothesisStatus.BLOCKED, HypothesisStatus.CLOSED}
    ),
    HypothesisStatus.BLOCKED: frozenset(
        {HypothesisStatus.TESTING, HypothesisStatus.CLOSED}
    ),
    HypothesisStatus.CLOSED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    status: HypothesisStatus
    confidence: Confidence
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    task_id: str
    scope_id: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    reason: str
    parent_hypothesis_id: str | None = None
    refutation_evidence_ids: tuple[str, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("statement must be non-empty")
        for value, name in (
            (self.hypothesis_id, "hypothesis_id"),
            (self.task_id, "task_id"),
            (self.scope_id, "scope_id"),
            (self.created_by, "created_by"),
            (self.reason, "reason"),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.parent_hypothesis_id == self.hypothesis_id:
            raise ValueError("hypothesis cannot be its own parent")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("hypothesis timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.confidence is Confidence.VERIFIED:
            raise ValueError("hypothesis confidence cannot be VERIFIED")
        supporting = set(self.supporting_evidence_ids)
        refuting = set(self.refutation_evidence_ids)
        if supporting & refuting:
            raise ValueError("supporting and refutation evidence must remain distinct")
        if not supporting.issubset(set(self.evidence_ids)):
            raise ValueError("supporting evidence must be referenced by evidence_ids")
        if not refuting.issubset(set(self.evidence_ids)):
            raise ValueError("refutation evidence must be referenced by evidence_ids")

    @classmethod
    def create(
        cls,
        *,
        statement: str,
        task_id: str,
        scope_id: str,
        created_by: str,
        reason: str,
        confidence: Confidence = Confidence.UNKNOWN,
        evidence_ids: Iterable[str] = (),
        claim_ids: Iterable[str] = (),
        parent_hypothesis_id: str | None = None,
        hypothesis_id: str | None = None,
        created_at: datetime | None = None,
    ) -> "Hypothesis":
        now = created_at or datetime.now(timezone.utc)
        return cls(
            hypothesis_id=hypothesis_id or new_id("hyp"),
            statement=statement,
            status=HypothesisStatus.PROPOSED,
            confidence=Confidence(confidence),
            evidence_ids=tuple(dict.fromkeys(evidence_ids)),
            claim_ids=tuple(dict.fromkeys(claim_ids)),
            task_id=task_id,
            scope_id=scope_id,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            reason=reason,
            parent_hypothesis_id=parent_hypothesis_id,
        )

    def transition(self, status: HypothesisStatus, *, reason: str) -> "Hypothesis":
        target = HypothesisStatus(status)
        if target not in _HYPOTHESIS_TRANSITIONS[self.status]:
            raise ValueError(
                f"invalid hypothesis transition: {self.status.value} -> {target.value}"
            )
        if not reason.strip():
            raise ValueError("transition reason must be non-empty")
        return replace(
            self,
            status=target,
            updated_at=datetime.now(timezone.utc),
            reason=reason,
        )

    def add_evidence(
        self,
        evidence_ids: Iterable[str],
        *,
        supporting: bool = False,
        refuting: bool = False,
    ) -> "Hypothesis":
        if supporting == refuting:
            raise ValueError("choose exactly one evidence role")
        additions = tuple(dict.fromkeys(str(item) for item in evidence_ids if str(item).strip()))
        if not additions:
            raise ValueError("at least one evidence_id is required")
        evidence = tuple(dict.fromkeys((*self.evidence_ids, *additions)))
        support = tuple(dict.fromkeys(
            (*self.supporting_evidence_ids, *additions)
        )) if supporting else self.supporting_evidence_ids
        refute = tuple(dict.fromkeys(
            (*self.refutation_evidence_ids, *additions)
        )) if refuting else self.refutation_evidence_ids
        if set(support) & set(refute):
            raise ValueError("evidence cannot support and refute the same hypothesis")
        return replace(
            self,
            evidence_ids=evidence,
            supporting_evidence_ids=support,
            refutation_evidence_ids=refute,
            updated_at=datetime.now(timezone.utc),
        )

    def record_test(
        self,
        *,
        verification: VerificationStatus,
        evidence_ids: Iterable[str],
        reason: str,
    ) -> "Hypothesis":
        ids = tuple(dict.fromkeys(evidence_ids))
        if not ids:
            raise ValueError("hypothesis testing requires evidence")
        verification = VerificationStatus(verification)
        if verification is VerificationStatus.PASS:
            updated = self.add_evidence(ids, supporting=True)
            return updated.transition(HypothesisStatus.SUPPORTED, reason=reason)
        if verification is VerificationStatus.FAIL:
            updated = self.add_evidence(ids, refuting=True)
            return updated.transition(HypothesisStatus.REFUTED, reason=reason)
        updated = replace(
            self,
            evidence_ids=tuple(dict.fromkeys((*self.evidence_ids, *ids))),
            updated_at=datetime.now(timezone.utc),
        )
        return updated.transition(HypothesisStatus.INCONCLUSIVE, reason=reason)


@dataclass(frozen=True, slots=True)
class RepairBudget:
    max_attempts: int
    max_files: int
    max_lines: int
    max_changes: int
    max_duration_seconds: float
    allowed_operations: frozenset[ScopeOperation]

    def __post_init__(self) -> None:
        values = (
            self.max_attempts,
            self.max_files,
            self.max_lines,
            self.max_changes,
            self.max_duration_seconds,
        )
        if any(value < 0 for value in values):
            raise ValueError("repair budget values cannot be negative")
        if not self.allowed_operations:
            raise ValueError("repair budget must explicitly allow operations")
        object.__setattr__(
            self,
            "allowed_operations",
            frozenset(ScopeOperation(item) for item in self.allowed_operations),
        )

    def allows_operation(self, operation: ScopeOperation) -> bool:
        return ScopeOperation(operation) in self.allowed_operations

    def check(
        self,
        *,
        attempt_number: int,
        files_changed: int = 0,
        lines_changed: int = 0,
        changes: int = 0,
        duration_seconds: float = 0.0,
    ) -> bool:
        values = (attempt_number, files_changed, lines_changed, changes, duration_seconds)
        if any(value < 0 for value in values):
            return False
        return (
            attempt_number <= self.max_attempts
            and files_changed <= self.max_files
            and lines_changed <= self.max_lines
            and changes <= self.max_changes
            and duration_seconds <= self.max_duration_seconds
        )


@dataclass(frozen=True, slots=True)
class RepairProposal:
    repair_id: str
    hypothesis_id: str
    task_id: str
    scope_id: str
    authorization_id: str | None
    description: str
    target: str
    operation: ScopeOperation
    expected_effect: str
    risk: str
    evidence_ids: tuple[str, ...]
    status: RepairStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.repair_id, "repair_id"),
            (self.hypothesis_id, "hypothesis_id"),
            (self.task_id, "task_id"),
            (self.scope_id, "scope_id"),
            (self.description, "description"),
            (self.target, "target"),
            (self.expected_effect, "expected_effect"),
            (self.risk, "risk"),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("repair timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        object.__setattr__(self, "operation", ScopeOperation(self.operation))

    @classmethod
    def propose(
        cls,
        *,
        hypothesis: Hypothesis,
        task: Task,
        scope: ScopeLock,
        description: str,
        target: str,
        operation: ScopeOperation,
        expected_effect: str,
        risk: str,
        evidence_ids: Iterable[str] = (),
        authorization_id: str | None = None,
        budget: RepairBudget | None = None,
        repair_id: str | None = None,
        created_at: datetime | None = None,
    ) -> "RepairProposal":
        now = created_at or datetime.now(timezone.utc)
        operation = ScopeOperation(operation)
        evidence = tuple(dict.fromkeys(evidence_ids))
        status = RepairStatus.PROPOSED
        if hypothesis.task_id != task.task_id or hypothesis.scope_id != scope.scope_id:
            status = RepairStatus.BLOCKED
        elif task.scope_id != scope.scope_id:
            status = RepairStatus.BLOCKED
        elif scope.current_status().value != "ACTIVE":
            status = RepairStatus.BLOCKED
        elif not scope.authorize(operation, target):
            status = RepairStatus.BLOCKED
        elif budget is not None and not budget.allows_operation(operation):
            status = RepairStatus.BLOCKED
        return cls(
            repair_id=repair_id or new_id("repair"),
            hypothesis_id=hypothesis.hypothesis_id,
            task_id=task.task_id,
            scope_id=scope.scope_id,
            authorization_id=authorization_id,
            description=description,
            target=target,
            operation=operation,
            expected_effect=expected_effect,
            risk=risk,
            evidence_ids=evidence,
            status=status,
            created_at=now,
            updated_at=now,
        )

    def transition(
        self,
        status: RepairStatus,
        *,
        reason: str = "",
    ) -> "RepairProposal":
        target = RepairStatus(status)
        allowed = {
            RepairStatus.PROPOSED: frozenset(
                {RepairStatus.APPROVED, RepairStatus.DENIED, RepairStatus.BLOCKED}
            ),
            RepairStatus.APPROVED: frozenset(
                {RepairStatus.EXECUTING, RepairStatus.DENIED, RepairStatus.BLOCKED}
            ),
            RepairStatus.DENIED: frozenset(),
            RepairStatus.BLOCKED: frozenset(),
            RepairStatus.EXECUTING: frozenset(
                {RepairStatus.SUCCEEDED, RepairStatus.FAILED, RepairStatus.ABORTED}
            ),
            RepairStatus.SUCCEEDED: frozenset(),
            RepairStatus.FAILED: frozenset(),
            RepairStatus.ABORTED: frozenset(),
        }[self.status]
        if target not in allowed:
            raise ValueError(
                f"invalid repair transition: {self.status.value} -> {target.value}"
            )
        return replace(self, status=target, updated_at=datetime.now(timezone.utc))

    def execution_authorized(
        self,
        *,
        task: Task,
        scope: ScopeLock,
        authorization: WriteAuthorization | None,
        authority_validator,
        current_time: datetime | None = None,
    ) -> bool:
        if self.status is not RepairStatus.APPROVED or authorization is None:
            return False
        if self.authorization_id != authorization.authorization_id:
            return False
        decision = check_authorization(
            authorization,
            task,
            scope,
            current_time=current_time,
            authority_validator=authority_validator,
        )
        return decision.result is AuthorizationCheckResult.AUTHORIZED


@dataclass(frozen=True, slots=True)
class VerificationResult:
    verification_id: str
    repair_id: str
    attempt_id: str
    status: VerificationStatus
    evidence_ids: tuple[str, ...]
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("verification reason must be non-empty")
        if self.created_at.tzinfo is None:
            raise ValueError("verification timestamp must be timezone-aware")

    @classmethod
    def create(
        cls,
        *,
        repair_id: str,
        attempt_id: str,
        status: VerificationStatus,
        evidence_ids: Iterable[str],
        reason: str,
        verification_id: str | None = None,
        created_at: datetime | None = None,
    ) -> "VerificationResult":
        ids = tuple(dict.fromkeys(evidence_ids))
        if not ids:
            raise ValueError("verification requires evidence")
        return cls(
            verification_id=verification_id or new_id("verify"),
            repair_id=repair_id,
            attempt_id=attempt_id,
            status=VerificationStatus(status),
            evidence_ids=ids,
            reason=reason,
            created_at=created_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True, slots=True)
class RepairAttempt:
    attempt_id: str
    repair_id: str
    attempt_number: int
    started_at: datetime
    finished_at: datetime | None
    status: RepairAttemptStatus
    changed_files: tuple[str, ...]
    changed_lines: int | None
    evidence_before: tuple[str, ...]
    evidence_after: tuple[str, ...]
    verification_result: VerificationResult | None
    failure_reason: str | None
    rollback_required: bool
    authorization_id: str | None

    def __post_init__(self) -> None:
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if self.finished_at is not None:
            if self.finished_at.tzinfo is None:
                raise ValueError("finished_at must be timezone-aware")
            if self.finished_at < self.started_at:
                raise ValueError("finished_at cannot precede started_at")
        if self.changed_lines is not None and self.changed_lines < 0:
            raise ValueError("changed_lines cannot be negative")
        if self.status is RepairAttemptStatus.FAILED and not (
            self.failure_reason and self.failure_reason.strip()
        ):
            raise ValueError("failed attempt requires failure_reason")
        if self.verification_result is not None:
            if self.verification_result.repair_id != self.repair_id:
                raise ValueError("verification repair_id mismatch")
            if self.verification_result.attempt_id != self.attempt_id:
                raise ValueError("verification attempt_id mismatch")

    @classmethod
    def start(
        cls,
        *,
        repair: RepairProposal,
        attempt_number: int,
        evidence_before: Iterable[str],
        authorization_id: str | None = None,
        budget: RepairBudget,
        started_at: datetime | None = None,
    ) -> "RepairAttempt":
        now = started_at or datetime.now(timezone.utc)
        if repair.status is not RepairStatus.APPROVED:
            return cls(
                attempt_id=new_id("attempt"),
                repair_id=repair.repair_id,
                attempt_number=attempt_number,
                started_at=now,
                finished_at=now,
                status=RepairAttemptStatus.BLOCKED,
                changed_files=(),
                changed_lines=0,
                evidence_before=tuple(evidence_before),
                evidence_after=(),
                verification_result=None,
                failure_reason="repair proposal is not approved",
                rollback_required=False,
                authorization_id=authorization_id,
            )
        if authorization_id is None:
            return cls(
                attempt_id=new_id("attempt"),
                repair_id=repair.repair_id,
                attempt_number=attempt_number,
                started_at=now,
                finished_at=now,
                status=RepairAttemptStatus.BLOCKED,
                changed_files=(),
                changed_lines=0,
                evidence_before=tuple(evidence_before),
                evidence_after=(),
                verification_result=None,
                failure_reason="authorization is required before execution",
                rollback_required=False,
                authorization_id=None,
            )
        if not budget.check(attempt_number=attempt_number):
            return cls(
                attempt_id=new_id("attempt"),
                repair_id=repair.repair_id,
                attempt_number=attempt_number,
                started_at=now,
                finished_at=now,
                status=RepairAttemptStatus.BLOCKED,
                changed_files=(),
                changed_lines=0,
                evidence_before=tuple(evidence_before),
                evidence_after=(),
                verification_result=None,
                failure_reason="repair budget exhausted or invalid",
                rollback_required=False,
                authorization_id=authorization_id,
            )
        return cls(
            attempt_id=new_id("attempt"),
            repair_id=repair.repair_id,
            attempt_number=attempt_number,
            started_at=now,
            finished_at=None,
            status=RepairAttemptStatus.STARTED,
            changed_files=(),
            changed_lines=None,
            evidence_before=tuple(evidence_before),
            evidence_after=(),
            verification_result=None,
            failure_reason=None,
            rollback_required=False,
            authorization_id=authorization_id,
        )

    def finish(
        self,
        *,
        status: RepairAttemptStatus,
        evidence_after: Iterable[str],
        verification_result: VerificationResult | None = None,
        changed_files: Iterable[str] = (),
        changed_lines: int | None = None,
        failure_reason: str | None = None,
        rollback_required: bool = False,
        finished_at: datetime | None = None,
        budget: RepairBudget | None = None,
    ) -> "RepairAttempt":
        if self.status is not RepairAttemptStatus.STARTED:
            raise ValueError("only STARTED attempts can be finished")
        target = RepairAttemptStatus(status)
        if target is RepairAttemptStatus.STARTED:
            raise ValueError("finish status cannot be STARTED")
        files = tuple(dict.fromkeys(changed_files))
        if budget is not None:
            end = finished_at or datetime.now(timezone.utc)
            duration = (end - self.started_at).total_seconds()
            if not budget.check(
                attempt_number=self.attempt_number,
                files_changed=len(files),
                lines_changed=changed_lines or 0,
                changes=len(files),
                duration_seconds=duration,
            ):
                raise ValueError("repair budget exceeded")
        if target is RepairAttemptStatus.FAILED and not (
            failure_reason and failure_reason.strip()
        ):
            raise ValueError("failed attempt requires failure_reason")
        end = finished_at or datetime.now(timezone.utc)
        if end < self.started_at:
            raise ValueError("finished_at cannot precede started_at")
        return replace(
            self,
            finished_at=end,
            status=target,
            changed_files=files,
            changed_lines=changed_lines,
            evidence_after=tuple(evidence_after),
            verification_result=verification_result,
            failure_reason=failure_reason,
            rollback_required=rollback_required,
        )


class RepairAttemptLedger:
    """Historial en memoria append-only; no ejecuta ni persiste reparaciones."""

    def __init__(self) -> None:
        self._attempts: dict[str, list[RepairAttempt]] = {}

    def add(self, attempt: RepairAttempt) -> RepairAttempt:
        history = self._attempts.setdefault(attempt.repair_id, [])
        if history and attempt.attempt_number != history[-1].attempt_number + 1:
            raise ValueError("attempt_number must be sequential and never restart")
        if not history and attempt.attempt_number != 1:
            raise ValueError("first attempt_number must be 1")
        if any(item.attempt_id == attempt.attempt_id for item in history):
            raise ValueError("attempt_id already exists")
        history.append(attempt)
        return attempt

    def history(self, repair_id: str) -> tuple[RepairAttempt, ...]:
        return tuple(self._attempts.get(repair_id, ()))

    def next_attempt_number(self, repair_id: str) -> int:
        history = self.history(repair_id)
        return history[-1].attempt_number + 1 if history else 1


def repair_audit_event(
    *,
    operation: str,
    repair_id: str | None = None,
    hypothesis_id: str | None = None,
    task_id: str | None = None,
    result: str,
) -> AuditEvent:
    """Crea un AuditEvent compatible con el EvidenceStore existente."""
    metadata = {
        key: value
        for key, value in {
            "repair_id": repair_id,
            "hypothesis_id": hypothesis_id,
        }.items()
        if value is not None
    }
    return AuditEvent.create(
        operation=operation,
        actor="supervisor.repair_contract",
        result=result,
        task_id=task_id,
        metadata=metadata,
    )


__all__ = [
    "Hypothesis",
    "HypothesisStatus",
    "RepairAttempt",
    "RepairAttemptLedger",
    "RepairAttemptStatus",
    "RepairBudget",
    "RepairProposal",
    "RepairStatus",
    "VerificationResult",
    "VerificationStatus",
    "repair_audit_event",
]
