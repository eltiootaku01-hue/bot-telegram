# -*- coding: utf-8 -*-
"""Motor pequeño de ciclo de vida para tareas de BOT-IA."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
from typing import Callable, Mapping
from uuid import uuid4


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


class TaskWaitReason(str, Enum):
    USER = "WAITING_USER"
    EXTERNAL = "WAITING_EXTERNAL"
    WEBCHAT = "WAITING_WEBCHAT"
    TIMER = "WAITING_TIMER"


class ReturnPolicy(str, Enum):
    RETURN_IF_VALID = "RETURN_IF_VALID"
    DISCARD_PARENT = "DISCARD_PARENT"
    NO_RETURN = "NO_RETURN"


class ResponseDisposition(str, Enum):
    ACCEPTED = "ACCEPTED"
    DISCARDED = "DISCARDED"


class TaskTransitionError(RuntimeError):
    """Una operación intentó una transición inválida de tarea."""


@dataclass(slots=True)
class Task:
    task_id: str
    requester: str
    task_type: str
    context: dict[str, object] = field(default_factory=dict)
    priority: int = 3
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    deadline: datetime | None = None
    timeout_policy: str = "mark_timed_out"
    parent_task_id: str | None = None
    interrupted_by: str | None = None
    return_policy: ReturnPolicy = ReturnPolicy.NO_RETURN
    wait_reason: TaskWaitReason | None = None


class TaskEngine:
    """Autoridad de ciclo de vida; no ejecuta WebChat ni posee una cola."""

    HIGH = 1
    MEDIUM = 2
    LOW = 3

    _LIVE_STATES = frozenset({
        TaskState.PENDING,
        TaskState.RUNNING,
        TaskState.WAITING,
        TaskState.INTERRUPTED,
    })
    _RESPONSE_STATES = frozenset({
        TaskState.RUNNING,
        TaskState.WAITING,
    })
    _COMPLETABLE_STATES = frozenset({
        TaskState.RUNNING,
        TaskState.WAITING,
        TaskState.INTERRUPTED,
    })

    def __init__(self, *, now_provider: Callable[[], datetime] | None = None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()

    def _now(self) -> datetime:
        value = self._now_provider()
        if value.tzinfo is None:
            raise ValueError("TaskEngine clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _priority(cls, priority: int) -> int:
        try:
            value = int(priority)
        except (TypeError, ValueError) as error:
            raise ValueError("priority must be HIGH=1, MEDIUM=2 or LOW=3") from error
        if value not in {cls.HIGH, cls.MEDIUM, cls.LOW}:
            raise ValueError("priority must be HIGH=1, MEDIUM=2 or LOW=3")
        return value

    def create_task(
        self,
        requester: str,
        task_type: str,
        *,
        context: Mapping[str, object] | None = None,
        priority: int = MEDIUM,
        deadline: datetime | None = None,
        timeout_policy: str = "mark_timed_out",
        parent_task_id: str | None = None,
        return_policy: ReturnPolicy = ReturnPolicy.NO_RETURN,
        task_id: str | None = None,
    ) -> Task:
        requester = self._text(requester, "requester")
        task_type = self._text(task_type, "task_type")
        task_id = self._text(task_id, "task_id") if task_id else uuid4().hex
        if deadline is not None:
            if deadline.tzinfo is None:
                raise ValueError("deadline must be timezone-aware")
            deadline = deadline.astimezone(timezone.utc)
        timeout_policy = self._text(timeout_policy, "timeout_policy")
        if not isinstance(return_policy, ReturnPolicy):
            try:
                return_policy = ReturnPolicy(str(return_policy))
            except ValueError as error:
                raise ValueError("invalid return_policy") from error

        priority = self._priority(priority)
        with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"task_id already exists: {task_id}")
            if parent_task_id is not None:
                parent_task_id = self._text(parent_task_id, "parent_task_id")
                if parent_task_id not in self._tasks:
                    raise ValueError(f"parent task does not exist: {parent_task_id}")
            task = Task(
                task_id=task_id,
                requester=requester,
                task_type=task_type,
                context=dict(context or {}),
                priority=priority,
                created_at=self._now(),
                deadline=deadline,
                timeout_policy=timeout_policy,
                parent_task_id=parent_task_id,
                return_policy=return_policy,
            )
            self._tasks[task_id] = task
            return task

    def get(self, task_id: str) -> Task | None:
        """Devuelve una copia: las mutaciones sólo pasan por TaskEngine."""
        return self.snapshot(task_id)

    def snapshot(self, task_id: str) -> Task | None:
        with self._lock:
            task = self._tasks.get(str(task_id).strip())
            if task is None:
                return None
            return Task(
                task.task_id, task.requester, task.task_type, dict(task.context),
                task.priority, task.state, task.created_at, task.started_at,
                task.deadline, task.timeout_policy, task.parent_task_id,
                task.interrupted_by, task.return_policy, task.wait_reason,
            )

    def is_valid(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(str(task_id).strip())
            if task is None:
                return False
            self._expire_if_needed_locked(task, self._now())
            return task.state in self._LIVE_STATES

    def start_task(self, task_id: str) -> Task:
        with self._lock:
            task = self._require(task_id)
            now = self._now()
            self._expire_if_needed_locked(task, now)
            if task.state is not TaskState.PENDING:
                raise TaskTransitionError(f"cannot start task in state {task.state.value}")
            if task.parent_task_id:
                parent = self._require(task.parent_task_id)
                self._expire_if_needed_locked(parent, now)
                if parent.state in {TaskState.RUNNING, TaskState.WAITING}:
                    self._interrupt_locked(parent, task.task_id)
            task.state = TaskState.RUNNING
            task.started_at = now
            task.wait_reason = None
            return task

    def wait(self, task_id: str, reason: TaskWaitReason) -> Task:
        if not isinstance(reason, TaskWaitReason):
            try:
                reason = TaskWaitReason(str(reason))
            except ValueError as error:
                raise ValueError("invalid task wait reason") from error
        with self._lock:
            task = self._require(task_id)
            self._expire_if_needed_locked(task, self._now())
            if task.state not in {TaskState.PENDING, TaskState.RUNNING}:
                raise TaskTransitionError(f"cannot wait task in state {task.state.value}")
            task.state = TaskState.WAITING
            task.wait_reason = reason
            return task

    def resume(self, task_id: str) -> Task:
        with self._lock:
            task = self._require(task_id)
            self._expire_if_needed_locked(task, self._now())
            if task.state not in {TaskState.WAITING, TaskState.INTERRUPTED}:
                raise TaskTransitionError(f"cannot resume task in state {task.state.value}")
            task.state = TaskState.RUNNING
            task.wait_reason = None
            task.interrupted_by = None
            return task

    def interrupt(self, task_id: str, *, interrupted_by: str) -> Task:
        interrupted_by = self._text(interrupted_by, "interrupted_by")
        with self._lock:
            task = self._require(task_id)
            self._expire_if_needed_locked(task, self._now())
            if task.state not in {TaskState.PENDING, TaskState.RUNNING, TaskState.WAITING}:
                raise TaskTransitionError(f"cannot interrupt task in state {task.state.value}")
            self._interrupt_locked(task, interrupted_by)
            return task

    def begin_cancellation(self, task_id: str) -> Task:
        with self._lock:
            task = self._require(task_id)
            self._expire_if_needed_locked(task, self._now())
            if task.state not in self._LIVE_STATES:
                raise TaskTransitionError(f"cannot cancel task in state {task.state.value}")
            task.state = TaskState.CANCELLING
            task.wait_reason = None
            return task

    def cancel(self, task_id: str) -> Task:
        with self._lock:
            task = self._require(task_id)
            self._expire_if_needed_locked(task, self._now())
            if task.state in self._LIVE_STATES:
                task.state = TaskState.CANCELLING
            if task.state is TaskState.CANCELLED:
                return task
            if task.state is not TaskState.CANCELLING:
                raise TaskTransitionError(f"cannot cancel task in state {task.state.value}")
            task.state = TaskState.CANCELLED
            task.wait_reason = None
            return task

    def fail(self, task_id: str) -> Task:
        with self._lock:
            task = self._require(task_id)
            if task.state not in self._LIVE_STATES | {TaskState.CANCELLING}:
                raise TaskTransitionError(f"cannot fail task in state {task.state.value}")
            task.state = TaskState.FAILED
            task.wait_reason = None
            return task

    def complete(self, task_id: str) -> Task:
        with self._lock:
            task = self._require(task_id)
            now = self._now()
            if self._expire_if_needed_locked(task, now):
                return task
            if task.state not in self._COMPLETABLE_STATES:
                raise TaskTransitionError(f"cannot complete task in state {task.state.value}")
            task.state = TaskState.COMPLETED
            task.wait_reason = None
            self._apply_return_policy_locked(task, now)
            return task

    def discard(self, task_id: str) -> Task:
        with self._lock:
            task = self._require(task_id)
            if task.state in {
                TaskState.COMPLETED,
                TaskState.FAILED,
                TaskState.TIMED_OUT,
                TaskState.CANCELLED,
            }:
                task.state = TaskState.DISCARDED
                task.wait_reason = None
                return task
            if task.state is TaskState.DISCARDED:
                return task
            raise TaskTransitionError(f"cannot discard active task in state {task.state.value}")

    def check_deadlines(self, *, now: datetime | None = None) -> tuple[str, ...]:
        with self._lock:
            current = now if now is not None else self._now()
            if current.tzinfo is None:
                raise ValueError("deadline check requires a timezone-aware datetime")
            current = current.astimezone(timezone.utc)
            expired = []
            for task in self._tasks.values():
                if self._expire_if_needed_locked(task, current):
                    expired.append(task.task_id)
            return tuple(expired)

    def validate_response(self, task_id: str) -> ResponseDisposition:
        """Valida un evento por task_id; nunca por texto o contexto."""
        with self._lock:
            task = self._tasks.get(str(task_id).strip())
            if task is None:
                return ResponseDisposition.DISCARDED
            if self._expire_if_needed_locked(task, self._now()):
                return ResponseDisposition.DISCARDED
            return (
                ResponseDisposition.ACCEPTED
                if task.state in self._RESPONSE_STATES
                else ResponseDisposition.DISCARDED
            )

    def _require(self, task_id: str) -> Task:
        clean = self._text(str(task_id), "task_id")
        task = self._tasks.get(clean)
        if task is None:
            raise KeyError(f"unknown task_id: {clean}")
        return task

    @staticmethod
    def _interrupt_locked(task: Task, interrupted_by: str) -> None:
        task.state = TaskState.INTERRUPTED
        task.interrupted_by = interrupted_by
        task.wait_reason = None

    @staticmethod
    def _expire_if_needed_locked(task: Task, now: datetime) -> bool:
        if task.state not in TaskEngine._LIVE_STATES:
            return False
        if task.deadline is None or now < task.deadline:
            return False
        task.state = TaskState.TIMED_OUT
        task.wait_reason = None
        return True

    def _apply_return_policy_locked(self, child: Task, now: datetime) -> None:
        parent_id = child.parent_task_id
        if not parent_id:
            return
        parent = self._tasks.get(parent_id)
        if parent is None:
            return
        self._expire_if_needed_locked(parent, now)
        if parent.state is not TaskState.INTERRUPTED:
            return
        if parent.return_policy is ReturnPolicy.RETURN_IF_VALID:
            parent.state = TaskState.RUNNING
            parent.interrupted_by = None
            parent.wait_reason = None
        elif parent.return_policy is ReturnPolicy.DISCARD_PARENT:
            parent.state = TaskState.DISCARDED
            parent.wait_reason = None


__all__ = [
    "ResponseDisposition",
    "ReturnPolicy",
    "Task",
    "TaskEngine",
    "TaskState",
    "TaskTransitionError",
    "TaskWaitReason",
]
