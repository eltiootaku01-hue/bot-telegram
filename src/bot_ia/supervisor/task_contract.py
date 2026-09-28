# -*- coding: utf-8 -*-
"""Contrato de tarea y máquina de estados del Supervisor.

Este módulo no ejecuta tareas ni sustituye TaskEngine/TaskScheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from .scope import ScopeLock


class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    INTERRUPTED = "INTERRUPTED"
    CANCELLING = "CANCELLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    DISCARDED = "DISCARDED"


class TaskPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskWaitReason(str, Enum):
    WAITING_USER = "WAITING_USER"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    WAITING_WEBCHAT = "WAITING_WEBCHAT"
    WAITING_TIMER = "WAITING_TIMER"


class ReturnPolicy(str, Enum):
    RETURN_IF_VALID = "RETURN_IF_VALID"
    DISCARD_PARENT = "DISCARD_PARENT"
    NO_RETURN = "NO_RETURN"


class ResponseDisposition(str, Enum):
    ACCEPTED = "ACCEPTED"
    DISCARDED = "DISCARDED"


class TaskTransitionError(RuntimeError):
    """Una transición de estado no está permitida."""


TERMINAL_STATES = frozenset(
    {
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.TIMED_OUT,
        TaskState.CANCELLED,
        TaskState.DISCARDED,
    }
)

_ALLOWED_TRANSITIONS = {
    TaskState.PENDING: frozenset({TaskState.RUNNING, TaskState.CANCELLED}),
    TaskState.RUNNING: frozenset(
        {
            TaskState.WAITING,
            TaskState.INTERRUPTED,
            TaskState.CANCELLING,
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.TIMED_OUT,
        }
    ),
    TaskState.WAITING: frozenset(
        {
            TaskState.RUNNING,
            TaskState.INTERRUPTED,
            TaskState.CANCELLING,
            TaskState.TIMED_OUT,
            TaskState.CANCELLED,
        }
    ),
    TaskState.INTERRUPTED: frozenset(
        {TaskState.RUNNING, TaskState.CANCELLED, TaskState.DISCARDED}
    ),
    TaskState.CANCELLING: frozenset({TaskState.CANCELLED, TaskState.FAILED}),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.TIMED_OUT: frozenset(),
    TaskState.CANCELLED: frozenset(),
    TaskState.DISCARDED: frozenset(),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_task_id() -> str:
    return f"task_{uuid4().hex}"


@dataclass(slots=True)
class Task:
    task_id: str
    requester: str
    task_type: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=_utc_now)
    started_at: datetime | None = None
    updated_at: datetime = field(default_factory=_utc_now)
    deadline: datetime | None = None
    timeout_policy: str = "mark_timed_out"
    parent_task_id: str | None = None
    interrupted_by: str | None = None
    return_policy: ReturnPolicy = ReturnPolicy.NO_RETURN
    wait_reason: TaskWaitReason | None = None
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    scope_id: str | None = None
    claim_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must be non-empty")
        if not self.requester.strip():
            raise ValueError("requester must be non-empty")
        if not self.task_type.strip():
            raise ValueError("task_type must be non-empty")
        for value, name in (
            (self.created_at, "created_at"),
            (self.started_at, "started_at"),
            (self.updated_at, "updated_at"),
            (self.deadline, "deadline"),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.deadline is not None:
            self.deadline = self.deadline.astimezone(timezone.utc)
        if self.state is TaskState.WAITING and self.wait_reason is None:
            raise ValueError("WAITING requires wait_reason")


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    result: Any = None
    completed_at: datetime = field(default_factory=_utc_now)


class TaskStateMachine:
    """Valida transiciones sin ejecutar ni persistir tareas."""

    @staticmethod
    def can_transition(current: TaskState, target: TaskState) -> bool:
        return TaskState(target) in _ALLOWED_TRANSITIONS[TaskState(current)]

    @staticmethod
    def transition(task: Task, target: TaskState) -> Task:
        target = TaskState(target)
        if not TaskStateMachine.can_transition(task.state, target):
            raise TaskTransitionError(
                f"invalid transition: {task.state.value} -> {target.value}"
            )
        if target is TaskState.WAITING and task.wait_reason is None:
            raise TaskTransitionError("WAITING requires wait_reason")
        task.state = target
        task.updated_at = _utc_now()
        if target is not TaskState.WAITING:
            task.wait_reason = None
        if target is TaskState.CANCELLING:
            task.error = None
        return task


class TaskContractStore:
    """Registro en memoria del contrato; no reemplaza TaskEngine."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def create(
        self,
        requester: str,
        task_type: str,
        *,
        task_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        deadline: datetime | None = None,
        timeout_policy: str = "mark_timed_out",
        parent_task_id: str | None = None,
        interrupted_by: str | None = None,
        return_policy: ReturnPolicy = ReturnPolicy.NO_RETURN,
        metadata: Mapping[str, Any] | None = None,
        scope_id: str | None = None,
        claim_ids: tuple[str, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        scope_lock: ScopeLock | None = None,
    ) -> Task:
        clean_id = task_id or _new_task_id()
        if clean_id in self._tasks:
            raise ValueError(f"task_id already exists: {clean_id}")
        if parent_task_id == clean_id:
            raise ValueError("task cannot be its own parent")
        if parent_task_id is not None:
            parent = self._tasks.get(parent_task_id)
            if parent is None:
                raise KeyError(f"parent task does not exist: {parent_task_id}")
            if parent.state in TERMINAL_STATES:
                raise ValueError("terminal task cannot become a parent")
            if self._would_create_cycle(clean_id, parent_task_id):
                raise ValueError("parent task cycle detected")
        if scope_id is not None and scope_lock is None:
            raise ValueError("scope_id requires a valid scope_lock")
        if scope_lock is not None:
            if scope_lock.task_id != clean_id:
                raise ValueError("scope_lock task_id does not match task_id")
            scope_id = scope_lock.scope_id
        task = Task(
            task_id=clean_id,
            requester=requester,
            task_type=task_type,
            context=dict(context or {}),
            priority=TaskPriority(priority),
            deadline=deadline,
            timeout_policy=timeout_policy,
            parent_task_id=parent_task_id,
            interrupted_by=interrupted_by,
            return_policy=ReturnPolicy(return_policy),
            metadata=dict(metadata or {}),
            scope_id=scope_id,
            claim_ids=tuple(claim_ids),
            evidence_ids=tuple(evidence_ids),
        )
        self._tasks[clean_id] = task
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def transition(self, task_id: str, target: TaskState) -> Task:
        return TaskStateMachine.transition(self._require(task_id), target)

    def validate_response(self, task_id: str) -> ResponseDisposition:
        task = self._tasks.get(task_id)
        if task is None or task.state not in {
            TaskState.RUNNING,
            TaskState.WAITING,
        }:
            return ResponseDisposition.DISCARDED
        return ResponseDisposition.ACCEPTED

    def attach_result(self, task_id: str, result: Any) -> TaskResult:
        task = self._require(task_id)
        if task.state in TERMINAL_STATES:
            raise TaskTransitionError(
                f"cannot attach result to terminal task: {task.state.value}"
            )
        task.result = result
        task.updated_at = _utc_now()
        return TaskResult(task_id=task.task_id, result=result)

    def _would_create_cycle(self, child_id: str, parent_id: str) -> bool:
        current = parent_id
        seen: set[str] = set()
        while current:
            if current == child_id or current in seen:
                return True
            seen.add(current)
            parent = self._tasks.get(current)
            if parent is None:
                return False
            current = parent.parent_task_id or ""
        return False

    def _require(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"unknown task_id: {task_id}")
        return task


def allowed_transitions(current: TaskState) -> frozenset[TaskState]:
    return _ALLOWED_TRANSITIONS[TaskState(current)]


__all__ = [
    "ResponseDisposition",
    "ReturnPolicy",
    "TERMINAL_STATES",
    "Task",
    "TaskContractStore",
    "TaskPriority",
    "TaskResult",
    "TaskState",
    "TaskStateMachine",
    "TaskTransitionError",
    "TaskWaitReason",
    "allowed_transitions",
]
