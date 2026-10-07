# -*- coding: utf-8 -*-
"""Bridge between logical TaskEngine lifecycle and physical WebChat state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import threading
from typing import Any, Protocol

from bot_ia.core.physical_resource_authority import (
    PhysicalReleaseEvidence,
    PhysicalResourceClaim,
    PhysicalResourceOwnershipError,
    PhysicalResourceSnapshot,
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
)
from bot_ia.core.task_engine import Task, TaskState


class ReconciliationStatus(str, Enum):
    ALIGNED = "ALIGNED"
    CANCELLATION_PENDING = "CANCELLATION_PENDING"
    TERMINATION_PENDING = "TERMINATION_PENDING"
    RELEASE_PENDING = "RELEASE_PENDING"
    QUARANTINED = "QUARANTINED"
    DIVERGED = "DIVERGED"


class TerminationState(str, Enum):
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class ReleaseState(str, Enum):
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PhysicalExecutionLike(Protocol):
    physical_resource_id: str
    claim_id: str
    execution_generation: int


class PhysicalLifecycleAdapter(Protocol):
    @property
    def authority(self) -> PhysicalWebChatResourceAuthority:
        ...

    @property
    def descriptor(self):
        ...

    def snapshot(self) -> PhysicalResourceSnapshot:
        ...

    def request_cancel(
        self,
        execution: PhysicalExecutionLike,
    ) -> PhysicalResourceSnapshot:
        ...

    def confirm_termination(
        self,
        execution: PhysicalExecutionLike,
        *,
        evidence: PhysicalReleaseEvidence,
    ) -> PhysicalResourceSnapshot:
        ...

    def quarantine_resource(
        self,
        execution: PhysicalExecutionLike,
        *,
        reason: str,
        evidence: str | None = None,
    ) -> PhysicalResourceSnapshot:
        ...


@dataclass(frozen=True, slots=True)
class PhysicalLifecycleReconciliationRecord:
    task_id: str
    physical_resource_id: str
    claim_id: str
    execution_generation: int
    logical_state: TaskState
    physical_state: PhysicalResourceState
    requested_action: str | None
    termination_state: TerminationState
    release_state: ReleaseState
    last_reconciled_at: datetime
    reconciliation_status: ReconciliationStatus
    last_error: str | None = None


class StaleReconciliationError(RuntimeError):
    """Raised when a late logical/physical event targets an old generation."""


class PhysicalLifecycleReconciliation:
    """Single bridge between logical lifecycle events and physical evidence.

    The bridge never owns a physical resource. It only delegates physical
    requests/evidence to the injected backend adapter and stores reconciliation
    metadata keyed by task id.
    """

    def __init__(
        self,
        authority: PhysicalWebChatResourceAuthority,
    ) -> None:
        if not isinstance(authority, PhysicalWebChatResourceAuthority):
            raise TypeError("authority must be PhysicalWebChatResourceAuthority")
        self._authority = authority
        self._records: dict[str, PhysicalLifecycleReconciliationRecord] = {}
        self._bindings: dict[str, tuple[PhysicalLifecycleAdapter, PhysicalExecutionLike]] = {}
        self._logical_tasks: dict[str, Task] = {}
        self._lock = threading.RLock()

    @property
    def authority(self) -> PhysicalWebChatResourceAuthority:
        return self._authority

    def observe_logical_task(self, task: Task) -> None:
        """Receive logical lifecycle events from TaskEngine."""
        if not isinstance(task, Task):
            raise TypeError("task must be Task")

        with self._lock:
            self._logical_tasks[task.task_id] = replace(task)
            binding = self._bindings.get(task.task_id)
            record = self._records.get(task.task_id)
            if record is not None:
                record = replace(
                    record,
                    logical_state=task.state,
                    last_reconciled_at=datetime.now(timezone.utc),
                )
                self._records[task.task_id] = record
            if binding is None or record is None:
                return

        self._update_from_logical_state(task, binding)

    def bind_execution(
        self,
        task: Task,
        adapter: PhysicalLifecycleAdapter,
        execution: PhysicalExecutionLike,
    ) -> PhysicalLifecycleReconciliationRecord:
        """Bind a logical task to one concrete physical execution tuple."""
        if not isinstance(task, Task):
            raise TypeError("task must be Task")
        if adapter.authority is not self._authority:
            raise ValueError("adapter must use the shared Physical Authority")
        if execution.physical_resource_id != adapter.descriptor.physical_resource_id:
            raise ValueError("execution does not match adapter descriptor")

        snapshot = adapter.snapshot()
        if snapshot.claim_id != execution.claim_id:
            raise StaleReconciliationError("execution claim is not current")
        if snapshot.execution_generation != execution.execution_generation:
            raise StaleReconciliationError("execution generation is not current")

        now = datetime.now(timezone.utc)
        record = PhysicalLifecycleReconciliationRecord(
            task_id=task.task_id,
            physical_resource_id=execution.physical_resource_id,
            claim_id=execution.claim_id,
            execution_generation=execution.execution_generation,
            logical_state=task.state,
            physical_state=snapshot.state,
            requested_action=None,
            termination_state=TerminationState.UNKNOWN,
            release_state=ReleaseState.UNKNOWN,
            last_reconciled_at=now,
            reconciliation_status=ReconciliationStatus.DIVERGED,
        )
        with self._lock:
            self._logical_tasks[task.task_id] = replace(task)
            self._bindings[task.task_id] = (adapter, execution)
            self._records[task.task_id] = record

        self.reconcile_task(task.task_id)
        if task.state in {TaskState.CANCELLING, TaskState.TIMED_OUT}:
            self.request_physical_cancel(task.task_id)
        return self.get_reconciliation(task.task_id)

    def request_physical_cancel(
        self,
        task_id: str,
    ) -> PhysicalLifecycleReconciliationRecord:
        """Request physical cancellation without implying termination."""
        adapter, execution, record = self._current_binding(task_id)

        with self._lock:
            if (
                record.requested_action == "CANCEL"
                and record.physical_state
                in {
                    PhysicalResourceState.CANCELLING,
                    PhysicalResourceState.QUARANTINED,
                }
            ):
                return record

        try:
            snapshot = adapter.snapshot()
            self._assert_current_generation(record, snapshot)
            snapshot = adapter.request_cancel(execution)
        except StaleReconciliationError:
            raise
        except Exception as error:
            return self._quarantine_after_failure(
                task_id,
                record,
                adapter,
                execution,
                reason="PHYSICAL_CANCEL_REQUEST_FAILED",
                error=error,
            )

        with self._lock:
            current = self._records[task_id]
            updated = replace(
                current,
                physical_state=snapshot.state,
                requested_action="CANCEL",
                last_reconciled_at=datetime.now(timezone.utc),
                reconciliation_status=(
                    ReconciliationStatus.CANCELLATION_PENDING
                    if snapshot.state is not PhysicalResourceState.QUARANTINED
                    else ReconciliationStatus.QUARANTINED
                ),
                last_error=None,
            )
            self._records[task_id] = updated
            return updated

    def record_termination(
        self,
        task_id: str,
        *,
        evidence: PhysicalReleaseEvidence,
    ) -> PhysicalLifecycleReconciliationRecord:
        """Record verified backend termination evidence and reconcile release."""
        if (
            not isinstance(evidence, PhysicalReleaseEvidence)
            or evidence.evidence_type.value != "TERMINATION"
        ):
            raise ValueError("typed termination evidence is required")
        adapter, execution, record = self._current_binding(task_id)
        try:
            snapshot = adapter.snapshot()
            self._assert_current_generation(record, snapshot)
            released = adapter.confirm_termination(
                execution,
                evidence=evidence,
            )
        except StaleReconciliationError:
            raise
        except Exception as error:
            return self._quarantine_after_failure(
                task_id,
                record,
                adapter,
                execution,
                reason="TERMINATION_EVIDENCE_FAILED",
                error=error,
                termination_failed=True,
            )

        with self._lock:
            current = self._records[task_id]
            status = self._status_for(
                current.logical_state,
                released.state,
            )
            updated = replace(
                current,
                physical_state=released.state,
                termination_state=TerminationState.CONFIRMED,
                release_state=(
                    ReleaseState.CONFIRMED
                    if released.state is PhysicalResourceState.AVAILABLE
                    else current.release_state
                ),
                last_reconciled_at=datetime.now(timezone.utc),
                reconciliation_status=status,
                last_error=None,
            )
            self._records[task_id] = updated
            return updated

    def record_release(
        self,
        task_id: str,
        *,
        evidence: PhysicalReleaseEvidence,
    ) -> PhysicalLifecycleReconciliationRecord:
        return self.record_termination(task_id, evidence=evidence)

    def record_quarantine(
        self,
        task_id: str,
        *,
        reason: str,
        evidence: str | None = None,
    ) -> PhysicalLifecycleReconciliationRecord:
        """Propagate physical quarantine into reconciliation metadata."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("quarantine reason is required")
        adapter, execution, record = self._current_binding(task_id)
        snapshot = adapter.snapshot()
        self._assert_current_generation(record, snapshot)
        quarantined = adapter.quarantine_resource(
            execution,
            reason=reason,
            evidence=evidence,
        )
        with self._lock:
            current = self._records[task_id]
            updated = replace(
                current,
                physical_state=quarantined.state,
                termination_state=(
                    current.termination_state
                    if current.termination_state is not TerminationState.UNKNOWN
                    else TerminationState.FAILED
                ),
                last_reconciled_at=datetime.now(timezone.utc),
                reconciliation_status=ReconciliationStatus.QUARANTINED,
                last_error=evidence or reason,
            )
            self._records[task_id] = updated
            return updated

    def record_backend_failure(
        self,
        task_id: str,
        *,
        evidence: str,
    ) -> PhysicalLifecycleReconciliationRecord:
        """Reconcile a backend failure without treating it as release evidence."""
        adapter, execution, record = self._current_binding(task_id)
        snapshot = adapter.snapshot()
        self._assert_current_generation(record, snapshot)
        if snapshot.state is PhysicalResourceState.AVAILABLE:
            with self._lock:
                updated = replace(
                    record,
                    physical_state=PhysicalResourceState.AVAILABLE,
                    termination_state=TerminationState.CONFIRMED,
                    release_state=ReleaseState.CONFIRMED,
                    last_reconciled_at=datetime.now(timezone.utc),
                    reconciliation_status=ReconciliationStatus.ALIGNED,
                    last_error=evidence,
                )
                self._records[task_id] = updated
                return updated
        return self.record_quarantine(
            task_id,
            reason="BACKEND_FAILURE_TERMINATION_UNCONFIRMED",
            evidence=evidence,
        )

    def reconcile_task(
        self,
        task_id: str,
    ) -> PhysicalLifecycleReconciliationRecord:
        """Reconcile current logical and physical truth without releasing anything."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise KeyError(f"no reconciliation for task: {task_id}")
            adapter, execution = self._bindings[task_id]
            logical = self._logical_tasks.get(task_id)
        snapshot = adapter.snapshot()
        self._assert_current_generation(record, snapshot)

        logical_state = logical.state if logical is not None else record.logical_state
        status = self._status_for(logical_state, snapshot.state)
        with self._lock:
            current = self._records[task_id]
            updated = replace(
                current,
                logical_state=logical_state,
                physical_state=snapshot.state,
                last_reconciled_at=datetime.now(timezone.utc),
                reconciliation_status=status,
            )
            self._records[task_id] = updated
            return updated

    def get_reconciliation(
        self,
        task_id: str,
    ) -> PhysicalLifecycleReconciliationRecord:
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise KeyError(f"no reconciliation for task: {task_id}")
            return replace(record)

    def _update_from_logical_state(
        self,
        task: Task,
        binding: tuple[PhysicalLifecycleAdapter, PhysicalExecutionLike],
    ) -> None:
        if task.state in {TaskState.CANCELLING, TaskState.TIMED_OUT}:
            self.request_physical_cancel(task.task_id)
            return
        self.reconcile_task(task.task_id)

    def _current_binding(
        self,
        task_id: str,
    ) -> tuple[
        PhysicalLifecycleAdapter,
        PhysicalExecutionLike,
        PhysicalLifecycleReconciliationRecord,
    ]:
        with self._lock:
            binding = self._bindings.get(task_id)
            record = self._records.get(task_id)
            if binding is None or record is None:
                raise KeyError(f"no physical execution bound to task: {task_id}")
            return binding[0], binding[1], record

    @staticmethod
    def _assert_current_generation(
        record: PhysicalLifecycleReconciliationRecord,
        snapshot: PhysicalResourceSnapshot,
    ) -> None:
        if (
            snapshot.physical_resource_id != record.physical_resource_id
            or snapshot.claim_id != record.claim_id
            or snapshot.execution_generation != record.execution_generation
        ):
            raise StaleReconciliationError(
                "stale reconciliation cannot affect a newer physical generation"
            )

    def _quarantine_after_failure(
        self,
        task_id: str,
        record: PhysicalLifecycleReconciliationRecord,
        adapter: PhysicalLifecycleAdapter,
        execution: PhysicalExecutionLike,
        *,
        reason: str,
        error: Exception,
        termination_failed: bool = False,
    ) -> PhysicalLifecycleReconciliationRecord:
        try:
            snapshot = adapter.snapshot()
            self._assert_current_generation(record, snapshot)
            quarantined = adapter.quarantine_resource(
                execution,
                reason=reason,
                evidence=f"{type(error).__name__}: {error}",
            )
            with self._lock:
                current = self._records[task_id]
                updated = replace(
                    current,
                    physical_state=quarantined.state,
                    termination_state=(
                        TerminationState.FAILED
                        if termination_failed
                        else current.termination_state
                    ),
                    release_state=ReleaseState.FAILED,
                    last_reconciled_at=datetime.now(timezone.utc),
                    reconciliation_status=ReconciliationStatus.QUARANTINED,
                    last_error=f"{type(error).__name__}: {error}",
                )
                self._records[task_id] = updated
                return updated
        except PhysicalResourceOwnershipError as stale_error:
            raise StaleReconciliationError(
                "physical ownership changed during reconciliation"
            ) from stale_error

    @staticmethod
    def _status_for(
        logical_state: TaskState,
        physical_state: PhysicalResourceState,
    ) -> ReconciliationStatus:
        logical_value = (
            logical_state.value
            if isinstance(logical_state, TaskState)
            else str(logical_state)
        )
        physical_value = (
            physical_state.value
            if isinstance(physical_state, PhysicalResourceState)
            else str(physical_state)
        )

        if physical_value == PhysicalResourceState.QUARANTINED.value:
            return ReconciliationStatus.QUARANTINED
        if physical_value in {
            PhysicalResourceState.CANCELLING.value,
            PhysicalResourceState.RELEASING.value,
        }:
            return (
                ReconciliationStatus.CANCELLATION_PENDING
                if physical_value == PhysicalResourceState.CANCELLING.value
                else ReconciliationStatus.RELEASE_PENDING
            )
        if logical_value in {
            TaskState.TIMED_OUT.value,
            TaskState.CANCELLING.value,
        }:
            if physical_value == PhysicalResourceState.AVAILABLE.value:
                return ReconciliationStatus.DIVERGED
            return ReconciliationStatus.TERMINATION_PENDING
        if logical_value == TaskState.COMPLETED.value:
            return (
                ReconciliationStatus.ALIGNED
                if physical_value == PhysicalResourceState.AVAILABLE.value
                else ReconciliationStatus.DIVERGED
            )
        if logical_value == TaskState.CANCELLED.value:
            return (
                ReconciliationStatus.ALIGNED
                if physical_value == PhysicalResourceState.AVAILABLE.value
                else ReconciliationStatus.DIVERGED
            )
        if logical_value == TaskState.FAILED.value:
            return (
                ReconciliationStatus.ALIGNED
                if physical_value == PhysicalResourceState.AVAILABLE.value
                else ReconciliationStatus.DIVERGED
            )
        if logical_value == TaskState.PENDING.value:
            return (
                ReconciliationStatus.ALIGNED
                if physical_value == PhysicalResourceState.AVAILABLE.value
                else ReconciliationStatus.DIVERGED
            )
        if logical_value in {
            TaskState.RUNNING.value,
            TaskState.WAITING.value,
            TaskState.INTERRUPTED.value,
        }:
            return (
                ReconciliationStatus.ALIGNED
                if physical_value in {
                    PhysicalResourceState.CLAIMING.value,
                    PhysicalResourceState.BUSY.value,
                }
                else ReconciliationStatus.DIVERGED
            )
        return ReconciliationStatus.DIVERGED



__all__ = [
    "PhysicalLifecycleReconciliation",
    "PhysicalLifecycleReconciliationRecord",
    "ReconciliationStatus",
    "ReleaseState",
    "StaleReconciliationError",
    "TerminationState",
]
