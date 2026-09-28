# -*- coding: utf-8 -*-
"""Observación read-only del runtime real de TaskEngine y TaskScheduler."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .boundary import TaskEngineBoundary
from .models import Evidence, EvidenceStatus, EvidenceType


@dataclass(frozen=True, slots=True)
class TaskRuntimeSnapshot:
    task_id: str
    requester: str
    state: str
    priority: int
    parent_task_id: str | None
    wait_reason: str | None
    created_at: str
    started_at: str | None
    deadline: str | None


@dataclass(frozen=True, slots=True)
class SchedulerRuntimeSnapshot:
    pending_task_ids: tuple[str, ...]
    active_task_ids: tuple[str, ...]


class RuntimeObservation:
    """Produce evidencia a partir de snapshots; nunca muta el runtime."""

    def __init__(self, boundary: TaskEngineBoundary) -> None:
        self._boundary = boundary

    def task(
        self,
        task_id: str,
        *,
        scenario: str = "",
        observed_at: datetime | None = None,
    ) -> Evidence:
        timestamp = _timestamp(observed_at)
        snapshot = self._boundary.observe_task(task_id)
        if snapshot is None:
            return Evidence.create(
                evidence_type=EvidenceType.RUNTIME_EVIDENCE,
                source="supervisor.runtime_observation",
                scope="task",
                result=EvidenceStatus.UNKNOWN,
                metadata={
                    "task_id": str(task_id),
                    "scenario": scenario,
                    "observation_timestamp": timestamp,
                    "reason": "unknown task_id",
                },
            )
        value = TaskRuntimeSnapshot(
            task_id=snapshot.task_id,
            requester=snapshot.requester,
            state=snapshot.state.value,
            priority=snapshot.priority,
            parent_task_id=snapshot.parent_task_id,
            wait_reason=(
                snapshot.wait_reason.value
                if snapshot.wait_reason is not None
                else None
            ),
            created_at=snapshot.created_at.isoformat(),
            started_at=(
                snapshot.started_at.isoformat()
                if snapshot.started_at is not None
                else None
            ),
            deadline=(
                snapshot.deadline.isoformat()
                if snapshot.deadline is not None
                else None
            ),
        )
        return Evidence.create(
            evidence_type=EvidenceType.RUNTIME_EVIDENCE,
            source="supervisor.runtime_observation",
            scope="task",
            result=EvidenceStatus.OBSERVED,
            metadata={
                "task_id": snapshot.task_id,
                "scenario": scenario,
                "observation_timestamp": timestamp,
                "snapshot": asdict(value),
            },
        )

    def scheduler(
        self,
        *,
        scenario: str = "",
        observed_at: datetime | None = None,
    ) -> Evidence:
        timestamp = _timestamp(observed_at)
        snapshot = self._boundary.observe_scheduler()
        if snapshot is None:
            return Evidence.create(
                evidence_type=EvidenceType.RUNTIME_EVIDENCE,
                source="supervisor.runtime_observation",
                scope="scheduler",
                result=EvidenceStatus.UNKNOWN,
                metadata={
                    "scenario": scenario,
                    "observation_timestamp": timestamp,
                    "reason": "scheduler observation unavailable",
                },
            )
        value = SchedulerRuntimeSnapshot(
            pending_task_ids=snapshot.pending_task_ids,
            active_task_ids=snapshot.active_task_ids,
        )
        return Evidence.create(
            evidence_type=EvidenceType.RUNTIME_EVIDENCE,
            source="supervisor.runtime_observation",
            scope="scheduler",
            result=EvidenceStatus.OBSERVED,
            metadata={
                "scenario": scenario,
                "observation_timestamp": timestamp,
                "snapshot": asdict(value),
            },
        )

    @staticmethod
    def transition(
        before: Evidence,
        after: Evidence,
        *,
        transition_source: str,
        scenario: str = "",
    ) -> Evidence:
        if before.type is not EvidenceType.RUNTIME_EVIDENCE:
            raise ValueError("before must be runtime evidence")
        if after.type is not EvidenceType.RUNTIME_EVIDENCE:
            raise ValueError("after must be runtime evidence")
        before_id = before.metadata.get("task_id")
        after_id = after.metadata.get("task_id")
        if before_id != after_id:
            return Evidence.create(
                evidence_type=EvidenceType.RUNTIME_EVIDENCE,
                source="supervisor.runtime_observation",
                scope="task",
                result=EvidenceStatus.BLOCKED,
                metadata={
                    "scenario": scenario,
                    "reason": "task_id mismatch between runtime snapshots",
                    "before_task_id": before_id,
                    "after_task_id": after_id,
                },
            )
        result = (
            EvidenceStatus.UNKNOWN
            if before.result is EvidenceStatus.UNKNOWN
            or after.result is EvidenceStatus.UNKNOWN
            else EvidenceStatus.TESTED
        )
        return Evidence.create(
            evidence_type=EvidenceType.RUNTIME_EVIDENCE,
            source="supervisor.runtime_observation",
            scope="task",
            result=result,
            metadata={
                "task_id": before_id,
                "scenario": scenario,
                "transition_source": transition_source,
                "before": before.metadata.get("snapshot", {}),
                "after": after.metadata.get("snapshot", {}),
            },
        )


def _timestamp(value: datetime | None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("observation timestamp must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat()
