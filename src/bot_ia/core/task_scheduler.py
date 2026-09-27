# -*- coding: utf-8 -*-
"""Router determinista de tareas; no ejecuta WebChat directamente."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Protocol

from bot_ia.core.task_engine import (
    ResponseDisposition,
    Task,
    TaskEngine,
    TaskState,
    TaskWaitReason,
)


class TaskRoute(str, Enum):
    LOCAL = "LOCAL"
    WEBCHAT = "WEBCHAT"


class TaskExecutor(Protocol):
    """Contrato mínimo del ejecutor seleccionado por el Scheduler."""

    def submit(self, task: Task) -> None:
        """Entrega una tarea al ejecutor."""

    def cancel(self, task_id: str) -> None:
        """Solicita cancelar una ejecución física."""


@dataclass(frozen=True, slots=True)
class ScheduledTask:
    task_id: str
    route: TaskRoute
    resource_key: str | None
    sequence: int


class TaskScheduler:
    """Selecciona, bloquea recursos y enruta sin crear otra cola.

    _pending es sólo un registro de tareas pendientes. La ejecución real
    continúa perteneciendo a los ejecutores, en particular a WebQueue para
    WebChat.
    """

    WEBCHAT_RESOURCE = "WEB_MESA_UNICA"
    STARVATION_BYPASS_AFTER = 3

    def __init__(self, task_engine: TaskEngine) -> None:
        self._engine = task_engine
        self._executors: dict[TaskRoute, TaskExecutor] = {}
        self._default_resources: dict[TaskRoute, str | None] = {}
        self._pending: dict[str, ScheduledTask] = {}
        self._registrations: dict[str, ScheduledTask] = {}
        self._active: dict[str, ScheduledTask] = {}
        self._resource_active: dict[str, str] = {}
        self._return_after_finish: set[str] = set()
        self._sequence = 0
        self._priority_streak: dict[str, tuple[int, int]] = {}
        self._lock = threading.RLock()

    @property
    def task_engine(self) -> TaskEngine:
        return self._engine

    def register_executor(
        self,
        route: TaskRoute,
        executor: TaskExecutor,
        *,
        default_resource_key: str | None = None,
    ) -> None:
        if not isinstance(route, TaskRoute):
            route = TaskRoute(str(route))
        if not hasattr(executor, "submit") or not hasattr(executor, "cancel"):
            raise TypeError("executor must provide submit() and cancel()")
        with self._lock:
            self._executors[route] = executor
            self._default_resources[route] = default_resource_key

    def schedule(
        self,
        task_id: str,
        route: TaskRoute,
        *,
        resource_key: str | None = None,
    ) -> ScheduledTask:
        task_id = str(task_id).strip()
        if not task_id:
            raise ValueError("task_id must be non-empty")
        if not isinstance(route, TaskRoute):
            route = TaskRoute(str(route))
        with self._lock:
            if route not in self._executors:
                raise RuntimeError(f"no executor registered for route {route.value}")
            if task_id in self._pending or task_id in self._active:
                raise ValueError(f"task already scheduled: {task_id}")
            task = self._engine.snapshot(task_id)
            if task is None:
                raise KeyError(f"unknown task_id: {task_id}")
            if task.state not in {
                TaskState.PENDING,
                TaskState.WAITING,
                TaskState.INTERRUPTED,
            }:
                raise ValueError(
                    f"task {task_id} cannot be scheduled from {task.state.value}"
                )
            self._sequence += 1
            item = ScheduledTask(
                task_id,
                route,
                (
                    resource_key
                    if resource_key is not None
                    else self._default_resources.get(route)
                ),
                self._sequence,
            )
            self._pending[task_id] = item
            self._registrations[task_id] = item
            return item

    def dispatch(self) -> tuple[str, ...]:
        """Inicia todas las tareas que tienen ruta y recurso disponibles."""
        started: list[str] = []
        with self._lock:
            self._engine.check_deadlines()
            while True:
                candidate = self._select_candidate_locked()
                if candidate is None:
                    return tuple(started)

                self._pending.pop(candidate.task_id, None)
                task = self._engine.snapshot(candidate.task_id)
                if task is None or not self._engine.is_valid(candidate.task_id):
                    continue

                try:
                    if task.state is TaskState.PENDING:
                        task = self._engine.start_task(candidate.task_id)
                    elif task.state in {
                        TaskState.WAITING,
                        TaskState.INTERRUPTED,
                    }:
                        task = self._engine.resume(candidate.task_id)
                    else:
                        continue
                except (KeyError, RuntimeError):
                    continue

                self._active[candidate.task_id] = candidate
                if candidate.resource_key is not None:
                    self._resource_active[candidate.resource_key] = candidate.task_id

                parent_id = task.parent_task_id
                if parent_id:
                    parent = self._active.get(parent_id)
                    if parent is not None:
                        self._request_parent_interruption_locked(parent)

                executor = self._executors[candidate.route]
                try:
                    executor.submit(task)
                except Exception:
                    self._active.pop(candidate.task_id, None)
                    if (
                        candidate.resource_key is not None
                        and self._resource_active.get(candidate.resource_key)
                        == candidate.task_id
                    ):
                        self._resource_active.pop(candidate.resource_key, None)
                    self._engine.fail(candidate.task_id)
                    continue

                self._record_start_locked(candidate)
                started.append(candidate.task_id)

    def cancel(self, task_id: str) -> Task:
        """Cancela sin reanimar ni volver a poner la tarea en pending."""
        task_id = str(task_id).strip()
        with self._lock:
            task = self._engine.snapshot(task_id)
            if task is None:
                raise KeyError(f"unknown task_id: {task_id}")
            was_active = task_id in self._active

            if task.state in {
                TaskState.PENDING,
                TaskState.RUNNING,
                TaskState.WAITING,
                TaskState.INTERRUPTED,
            }:
                task = self._engine.cancel(task_id)
            elif task.state is TaskState.CANCELLED:
                return task
            else:
                raise RuntimeError(
                    f"task {task_id} cannot be cancelled from {task.state.value}"
                )

            self._pending.pop(task_id, None)
            self._return_after_finish.discard(task_id)

            if was_active:
                scheduled = self._active.get(task_id)
                if scheduled is not None:
                    try:
                        self._executors[scheduled.route].cancel(task_id)
                    except Exception:
                        pass
            else:
                self.dispatch()
            return task

    def accept_response(self, task_id: str) -> ResponseDisposition:
        """Valida por task_id, completa y prepara el retorno del parent."""
        task_id = str(task_id).strip()
        with self._lock:
            disposition = self._engine.validate_response(task_id)
            if disposition is not ResponseDisposition.ACCEPTED:
                return disposition

            completed = self._engine.complete(task_id)
            parent_id = completed.parent_task_id
            if parent_id and self._engine.can_return(parent_id):
                if parent_id in self._active:
                    self._return_after_finish.add(parent_id)
                elif parent_id not in self._pending:
                    self._enqueue_parent_locked(parent_id)

            self.dispatch()
            return disposition

    def fail_from_executor(self, task_id: str) -> Task:
        """Sincroniza el fallo físico sin revivir una tarea cancelada."""
        task_id = str(task_id).strip()
        with self._lock:
            task = self._engine.snapshot(task_id)
            if task is None:
                raise KeyError(f"unknown task_id: {task_id}")
            if task.state in {
                TaskState.PENDING,
                TaskState.RUNNING,
                TaskState.WAITING,
            }:
                self._engine.fail(task_id)
            self.execution_finished(task_id)
            result = self._engine.snapshot(task_id)
            if result is None:
                raise KeyError(f"unknown task_id: {task_id}")
            return result

    def execution_finished(self, task_id: str) -> None:
        """Libera el recurso tras finalizar físicamente el ejecutor."""
        task_id = str(task_id).strip()
        with self._lock:
            scheduled = self._active.pop(task_id, None)
            if scheduled is None:
                return

            if (
                scheduled.resource_key is not None
                and self._resource_active.get(scheduled.resource_key)
                == task_id
            ):
                self._resource_active.pop(scheduled.resource_key, None)

            should_return = task_id in self._return_after_finish
            self._return_after_finish.discard(task_id)

            if should_return and self._engine.can_return(task_id):
                self._enqueue_parent_locked(task_id)

            self.dispatch()

    def wait(self, task_id: str, reason: TaskWaitReason) -> Task:
        with self._lock:
            return self._engine.wait(task_id, reason)

    def snapshot(self, task_id: str) -> ScheduledTask | None:
        with self._lock:
            return (
                self._pending.get(task_id)
                or self._active.get(task_id)
                or self._registrations.get(task_id)
            )

    def active_task_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._active))

    def pending_task_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                item.task_id
                for item in sorted(
                    self._pending.values(),
                    key=lambda item: item.sequence,
                )
            )

    def _enqueue_parent_locked(self, task_id: str) -> None:
        registration = self._registrations.get(task_id)
        if registration is None:
            return
        if task_id in self._pending or task_id in self._active:
            return
        self._sequence += 1
        self._pending[task_id] = ScheduledTask(
            task_id,
            registration.route,
            registration.resource_key,
            self._sequence,
        )

    def _request_parent_interruption_locked(
        self,
        parent: ScheduledTask,
    ) -> None:
        parent_executor = self._executors[parent.route]
        try:
            parent_executor.cancel(parent.task_id)
        except Exception:
            pass

    def _select_candidate_locked(self) -> ScheduledTask | None:
        candidates: list[ScheduledTask] = []

        for item in self._pending.values():
            task = self._engine.snapshot(item.task_id)
            if task is None or not self._engine.is_valid(item.task_id):
                continue

            if (
                item.resource_key is not None
                and item.resource_key in self._resource_active
            ):
                if task.state is TaskState.PENDING:
                    reason = (
                        TaskWaitReason.WEBCHAT
                        if item.route is TaskRoute.WEBCHAT
                        else TaskWaitReason.EXTERNAL
                    )
                    try:
                        self._engine.wait(item.task_id, reason)
                    except RuntimeError:
                        pass
                continue

            executor = self._executors[item.route]
            available = getattr(executor, "is_available", None)
            if callable(available) and not bool(available()):
                if (
                    task.state is TaskState.PENDING
                    and item.route is TaskRoute.WEBCHAT
                ):
                    try:
                        self._engine.wait(
                            item.task_id,
                            TaskWaitReason.WEBCHAT,
                        )
                    except RuntimeError:
                        pass
                continue

            candidates.append(item)

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                self._engine.snapshot(item.task_id).priority,
                item.sequence,
            )
        )
        first = candidates[0]
        resource = first.resource_key
        if resource is None:
            return first

        streak = self._priority_streak.get(resource)
        if streak is not None and streak[1] >= self.STARVATION_BYPASS_AFTER:
            oldest_lower = min(
                (
                    item
                    for item in candidates
                    if self._engine.snapshot(item.task_id).priority
                    > streak[0]
                ),
                key=lambda item: item.sequence,
                default=None,
            )
            if oldest_lower is not None:
                return oldest_lower
        return first

    def _record_start_locked(self, item: ScheduledTask) -> None:
        if item.resource_key is None:
            return

        task = self._engine.snapshot(item.task_id)
        if task is None:
            return

        previous = self._priority_streak.get(item.resource_key)
        if previous is None:
            self._priority_streak[item.resource_key] = (task.priority, 1)
            return

        previous_priority, count = previous
        if task.priority < previous_priority:
            self._priority_streak[item.resource_key] = (
                task.priority,
                1,
            )
        elif task.priority == previous_priority:
            self._priority_streak[item.resource_key] = (
                task.priority,
                count + 1,
            )
        else:
            self._priority_streak[item.resource_key] = (
                task.priority,
                1,
            )


class WebChatTaskExecutor:
    """Adaptador fino que entrega al WebQueue existente."""

    def __init__(self, web_queue: object) -> None:
        self._web_queue = web_queue

    def submit(self, task: Task) -> None:
        context = task.context
        self._web_queue.enqueue_bot_message(
            bot_name=str(context["bot_name"]),
            ticket_id=task.task_id,
            action=str(context["action"]),
            message=str(context["message"]),
            user=str(context.get("user", "@usuario")),
            channel=str(context.get("channel", "/general")),
        )

    def cancel(self, task_id: str) -> None:
        cancel = getattr(self._web_queue, "cancel_ticket", None)
        if callable(cancel):
            cancel(task_id)

    def is_available(self) -> bool:
        if bool(getattr(self._web_queue, "circuit_open", False)):
            return False
        if bool(getattr(self._web_queue, "is_busy", False)):
            return False
        message_queue = getattr(self._web_queue, "msg_queue", None)
        empty = getattr(message_queue, "empty", None)
        return True if not callable(empty) else bool(empty())


__all__ = [
    "ScheduledTask",
    "TaskExecutor",
    "TaskRoute",
    "TaskScheduler",
    "WebChatTaskExecutor",
]
