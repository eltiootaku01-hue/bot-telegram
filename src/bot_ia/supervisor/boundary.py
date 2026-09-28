# -*- coding: utf-8 -*-
"""Frontera contractual y read-only entre Supervisor y runtime de tareas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from bot_ia.core.task_engine import (
    Task as EngineTask,
    TaskEngine,
    TaskState as EngineTaskState,
)
from bot_ia.core.task_scheduler import TaskScheduler

from .authorization import (
    AuthorizationCheckResult,
    AuthorityValidator,
    WriteAuthorization,
    check_authorization,
)
from .scope import ScopeLock, ScopeOperation


class SupervisorCommand(str, Enum):
    OBSERVE = "OBSERVE"
    VALIDATE = "VALIDATE"
    REQUEST = "REQUEST"
    BLOCK = "BLOCK"
    CANCEL_REQUEST = "CANCEL_REQUEST"
    VERIFY = "VERIFY"


class BoundaryDecision(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    DENIED = "DENIED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class TaskObservation:
    """Snapshot mínimo; no contiene una referencia mutable al TaskEngine."""

    task_id: str
    requester: str
    state: EngineTaskState
    priority: int
    parent_task_id: str | None
    wait_reason: object | None
    created_at: datetime
    started_at: datetime | None
    deadline: datetime | None


@dataclass(frozen=True, slots=True)
class SchedulerObservation:
    pending_task_ids: tuple[str, ...]
    active_task_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoundaryResult:
    decision: BoundaryDecision
    task_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class _AuthorizationTaskView:
    """Adaptador de identidad; no representa un segundo lifecycle."""

    task_id: str
    requester: str
    scope_id: str | None


class TaskEngineBoundary:
    """Valida coordinación sin poseer lifecycle, scheduling ni ejecución."""

    def __init__(
        self,
        task_engine: TaskEngine,
        task_scheduler: TaskScheduler | None = None,
    ) -> None:
        if not isinstance(task_engine, TaskEngine):
            raise TypeError("task_engine must be a TaskEngine")
        if task_scheduler is not None and task_scheduler.task_engine is not task_engine:
            raise ValueError("TaskScheduler must use the same TaskEngine")
        self._engine = task_engine
        self._scheduler = task_scheduler

    def observe_task(self, task_id: str) -> TaskObservation | None:
        """Observa sin cambiar TaskEngine ni Scheduler."""
        task = self._engine.snapshot(task_id)
        if task is None:
            return None
        return self._observation(task)

    def observe_scheduler(self) -> SchedulerObservation | None:
        """Observa el scheduler existente; no selecciona ni despacha tareas."""
        if self._scheduler is None:
            return None
        return SchedulerObservation(
            pending_task_ids=self._scheduler.pending_task_ids(),
            active_task_ids=self._scheduler.active_task_ids(),
        )

    def validate_request(
        self,
        task_id: str,
        command: SupervisorCommand,
        *,
        scope: ScopeLock | None = None,
        authorization: WriteAuthorization | None = None,
        operation: ScopeOperation | None = None,
        target: str | None = None,
        current_time: datetime | None = None,
        authority_validator: AuthorityValidator | None = None,
        supervisor_identity: str | None = None,
    ) -> BoundaryResult:
        """Valida una solicitud contractual; nunca ejecuta ni muta un runtime."""
        clean_id = str(task_id).strip()
        if not clean_id:
            return BoundaryResult(BoundaryDecision.INVALID, clean_id, "task_id is empty")
        try:
            command = SupervisorCommand(command)
        except ValueError:
            return BoundaryResult(BoundaryDecision.UNKNOWN, clean_id, "unknown Supervisor command")

        task = self._engine.snapshot(clean_id)
        if task is None:
            return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "unknown task_id")

        if command is SupervisorCommand.OBSERVE:
            return BoundaryResult(BoundaryDecision.ALLOWED, clean_id, "observation is read-only")

        if task.state not in set(EngineTaskState):
            return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "unknown task state")

        if command in {SupervisorCommand.REQUEST, SupervisorCommand.CANCEL_REQUEST}:
            if task.state in {
                EngineTaskState.COMPLETED,
                EngineTaskState.FAILED,
                EngineTaskState.TIMED_OUT,
                EngineTaskState.CANCELLED,
                EngineTaskState.DISCARDED,
            }:
                return BoundaryResult(
                    BoundaryDecision.BLOCKED,
                    clean_id,
                    "terminal task cannot receive an operational request",
                )

        if scope is not None:
            if scope.task_id != clean_id:
                return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "scope task_id mismatch")
            if scope.current_status().value != "ACTIVE":
                return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "scope is not active")
            if operation is not None:
                if target is None:
                    return BoundaryResult(BoundaryDecision.INVALID, clean_id, "target is required with operation")
                if not scope.authorize(operation, target):
                    return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "operation or target exceeds ScopeLock")
        elif operation is not None or target is not None:
            return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "operation/target requires ScopeLock")

        if authorization is not None:
            if scope is None:
                return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "authorization requires ScopeLock")
            if operation is None or target is None:
                return BoundaryResult(BoundaryDecision.INVALID, clean_id, "authorization requires operation and target")
            if authorization.operation is not operation or authorization.target != target:
                return BoundaryResult(BoundaryDecision.BLOCKED, clean_id, "authorization operation or target mismatch")
            decision = check_authorization(
                authorization,
                _AuthorizationTaskView(clean_id, task.requester, scope.scope_id),
                scope,
                current_time=current_time,
                authority_validator=authority_validator,
                supervisor_identity=supervisor_identity,
            )
            if decision.result is not AuthorizationCheckResult.AUTHORIZED:
                identity_or_binding = {
                    "task identity mismatch",
                    "scope identity mismatch",
                    "requester mismatch",
                    "task is not bound to the authorization scope",
                    "operation or target exceeds ScopeLock",
                }
                boundary = (
                    BoundaryDecision.BLOCKED
                    if decision.reason in identity_or_binding
                    else (
                        BoundaryDecision.DENIED
                        if decision.result in {
                            AuthorizationCheckResult.DENIED,
                            AuthorizationCheckResult.REVOKED,
                            AuthorizationCheckResult.EXPIRED,
                        }
                        else BoundaryDecision.INVALID
                    )
                )
                return BoundaryResult(boundary, clean_id, decision.reason)
        elif operation is not None:
            return BoundaryResult(BoundaryDecision.DENIED, clean_id, "authorization is required for an operational request")

        return BoundaryResult(BoundaryDecision.ALLOWED, clean_id, "contractual request accepted; execution remains external")

    @staticmethod
    def _observation(task: EngineTask) -> TaskObservation:
        return TaskObservation(
            task_id=task.task_id,
            requester=task.requester,
            state=task.state,
            priority=task.priority,
            parent_task_id=task.parent_task_id,
            wait_reason=task.wait_reason,
            created_at=task.created_at,
            started_at=task.started_at,
            deadline=task.deadline,
        )


__all__ = [
    "BoundaryDecision",
    "BoundaryResult",
    "SchedulerObservation",
    "SupervisorCommand",
    "TaskEngineBoundary",
    "TaskObservation",
]
