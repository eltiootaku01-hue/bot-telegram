# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import unittest

from bot_ia.core.task_engine import (
    ResponseDisposition,
    ReturnPolicy,
    TaskEngine,
    TaskState,
)
from bot_ia.core.task_scheduler import (
    TaskRoute,
    TaskScheduler,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class FakeExecutor:
    def __init__(self) -> None:
        self.started = []
        self.cancelled = []
        self.available = True

    def submit(self, task) -> None:
        self.started.append(task.task_id)

    def cancel(self, task_id: str) -> None:
        self.cancelled.append(task_id)

    def is_available(self) -> bool:
        return self.available


class TaskSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.engine = TaskEngine(now_provider=self.clock.now)
        self.scheduler = TaskScheduler(self.engine)
        self.web = FakeExecutor()
        self.local = FakeExecutor()
        self.scheduler.register_executor(
            TaskRoute.WEBCHAT,
            self.web,
            default_resource_key=TaskScheduler.WEBCHAT_RESOURCE,
        )
        self.scheduler.register_executor(
            TaskRoute.LOCAL,
            self.local,
        )

    def create(
        self,
        task_id: str,
        *,
        route: TaskRoute,
        priority: int = TaskEngine.MEDIUM,
        requester: str = "user",
        context=None,
        deadline=None,
        parent_task_id=None,
        return_policy=ReturnPolicy.NO_RETURN,
        resource_key=None,
    ):
        task = self.engine.create_task(
            requester,
            "test",
            task_id=task_id,
            priority=priority,
            context=context or {"name": task_id},
            deadline=deadline,
            parent_task_id=parent_task_id,
            return_policy=return_policy,
        )
        self.scheduler.schedule(
            task.task_id,
            route,
            resource_key=resource_key,
        )
        return task

    def test_priority_high_before_low(self) -> None:
        low = self.create(
            "low",
            route=TaskRoute.WEBCHAT,
            priority=TaskEngine.LOW,
        )
        high = self.create(
            "high",
            route=TaskRoute.WEBCHAT,
            priority=TaskEngine.HIGH,
        )
        self.assertEqual(("high",), self.scheduler.dispatch())
        self.assertEqual(["high"], self.web.started)
        self.assertEqual(TaskState.PENDING, self.engine.snapshot(low.task_id).state)

    def test_fifo_within_same_priority(self) -> None:
        self.create("a", route=TaskRoute.WEBCHAT, priority=TaskEngine.HIGH)
        self.create("b", route=TaskRoute.WEBCHAT, priority=TaskEngine.HIGH)
        self.assertEqual(("a",), self.scheduler.dispatch())
        self.scheduler.execution_finished("a")
        self.assertEqual(["a", "b"], self.web.started)

    def test_webchat_is_exclusive(self) -> None:
        self.create("a", route=TaskRoute.WEBCHAT)
        self.create("b", route=TaskRoute.WEBCHAT)
        self.assertEqual(("a",), self.scheduler.dispatch())
        self.assertEqual(
            TaskState.WAITING,
            self.engine.snapshot("b").state,
        )
        self.assertEqual(
            "WAITING_WEBCHAT",
            self.engine.snapshot("b").wait_reason.value,
        )
        self.scheduler.execution_finished("a")
        self.assertEqual(["a", "b"], self.web.started)

    def test_local_independent_resource_runs_with_webchat(self) -> None:
        self.create("web", route=TaskRoute.WEBCHAT, priority=TaskEngine.HIGH)
        self.create("local", route=TaskRoute.LOCAL, priority=TaskEngine.MEDIUM)
        started = self.scheduler.dispatch()
        self.assertEqual(
            {"web", "local"},
            set(started),
        )
        self.assertEqual(["web"], self.web.started)
        self.assertEqual(["local"], self.local.started)

    def test_pending_cancel_never_executes(self) -> None:
        self.create("a", route=TaskRoute.WEBCHAT)
        self.scheduler.cancel("a")
        self.assertEqual([], self.web.started)
        self.assertEqual(TaskState.CANCELLED, self.engine.snapshot("a").state)

    def test_waiting_cancel_transitions_to_cancelled(self) -> None:
        self.create("a", route=TaskRoute.WEBCHAT)
        self.create("b", route=TaskRoute.WEBCHAT)
        self.scheduler.dispatch()
        self.scheduler.cancel("b")
        self.assertEqual(TaskState.CANCELLED, self.engine.snapshot("b").state)
        self.assertNotIn("b", self.scheduler.pending_task_ids())

    def test_late_response_is_discarded_after_cancel(self) -> None:
        self.create("a", route=TaskRoute.WEBCHAT)
        self.scheduler.dispatch()
        self.scheduler.cancel("a")
        self.assertEqual(
            ResponseDisposition.DISCARDED,
            self.scheduler.accept_response("a"),
        )

    def test_parent_child_returns_only_after_parent_execution_finishes(self) -> None:
        parent = self.create(
            "parent",
            route=TaskRoute.LOCAL,
            return_policy=ReturnPolicy.RETURN_IF_VALID,
            resource_key="parent-resource",
        )
        child = self.create(
            "child",
            route=TaskRoute.LOCAL,
            parent_task_id=parent.task_id,
            resource_key="child-resource",
        )
        self.scheduler.dispatch()
        self.assertEqual(
            TaskState.INTERRUPTED,
            self.engine.snapshot(parent.task_id).state,
        )
        self.assertEqual(
            ["parent", "child"],
            self.local.started,
        )
        self.scheduler.accept_response(child.task_id)
        self.assertEqual(
            TaskState.INTERRUPTED,
            self.engine.snapshot(parent.task_id).state,
        )
        self.assertNotIn("parent", self.scheduler.pending_task_ids())
        self.scheduler.execution_finished(parent.task_id)
        self.assertEqual(
            TaskState.RUNNING,
            self.engine.snapshot(parent.task_id).state,
        )
        self.assertEqual(
            ["parent", "child", "parent"],
            self.local.started,
        )

    def test_expired_parent_is_not_returned(self) -> None:
        parent = self.create(
            "parent",
            route=TaskRoute.LOCAL,
            return_policy=ReturnPolicy.RETURN_IF_VALID,
            deadline=self.clock.now() + timedelta(seconds=5),
            resource_key="parent-resource",
        )
        child = self.create(
            "child",
            route=TaskRoute.LOCAL,
            parent_task_id=parent.task_id,
            resource_key="child-resource",
        )
        self.scheduler.dispatch()
        self.scheduler.accept_response(child.task_id)
        self.clock.advance(6)
        self.scheduler.execution_finished(parent.task_id)
        self.assertEqual(
            TaskState.TIMED_OUT,
            self.engine.snapshot(parent.task_id).state,
        )
        self.assertEqual(["parent", "child"], self.local.started)

    def test_cooldown_does_not_extend_action_deadline(self) -> None:
        task = self.create(
            "a",
            route=TaskRoute.WEBCHAT,
            deadline=self.clock.now() + timedelta(seconds=1),
        )
        self.scheduler.dispatch()
        self.clock.advance(2)
        self.engine.check_deadlines()
        self.assertEqual(
            TaskState.TIMED_OUT,
            self.engine.snapshot(task.task_id).state,
        )
        self.scheduler.execution_finished(task.task_id)
        self.assertEqual(["a"], self.web.started)
        self.assertEqual(TaskState.TIMED_OUT, self.engine.snapshot("a").state)

    def test_webchat_cooldown_wait_does_not_extend_deadline(self) -> None:
        task = self.create(
            "cooling",
            route=TaskRoute.WEBCHAT,
            deadline=self.clock.now() + timedelta(seconds=3),
        )
        self.web.available = False
        self.assertEqual((), self.scheduler.dispatch())
        self.assertEqual(
            TaskState.WAITING,
            self.engine.snapshot(task.task_id).state,
        )
        self.assertEqual(
            "WAITING_WEBCHAT",
            self.engine.snapshot(task.task_id).wait_reason.value,
        )
        self.clock.advance(4)
        self.web.available = True
        self.assertEqual((), self.scheduler.dispatch())
        self.assertEqual(
            TaskState.TIMED_OUT,
            self.engine.snapshot(task.task_id).state,
        )

    def test_duplicate_task_cannot_execute_twice(self) -> None:
        self.create("a", route=TaskRoute.WEBCHAT)
        with self.assertRaises(ValueError):
            self.scheduler.schedule("a", TaskRoute.WEBCHAT)
        self.scheduler.dispatch()
        self.assertEqual(["a"], self.web.started)

    def test_requester_and_context_do_not_cross_lifecycle(self) -> None:
        first = self.create(
            "first",
            route=TaskRoute.LOCAL,
            requester="same",
            context={"text": "same"},
            resource_key="first",
        )
        second = self.create(
            "second",
            route=TaskRoute.LOCAL,
            requester="same",
            context={"text": "same"},
            resource_key="second",
        )
        self.scheduler.dispatch()
        self.scheduler.cancel(first.task_id)
        self.assertEqual(TaskState.CANCELLED, self.engine.snapshot(first.task_id).state)
        self.assertEqual(TaskState.RUNNING, self.engine.snapshot(second.task_id).state)

    def test_starvation_bypass_after_three_higher_priority_dispatches(self) -> None:
        self.create(
            "low",
            route=TaskRoute.WEBCHAT,
            priority=TaskEngine.LOW,
        )
        for index in range(3):
            self.create(
                f"high-{index}",
                route=TaskRoute.WEBCHAT,
                priority=TaskEngine.HIGH,
            )
        self.scheduler.dispatch()
        self.scheduler.execution_finished("high-0")
        self.scheduler.execution_finished("high-1")
        self.scheduler.execution_finished("high-2")
        self.assertEqual(
            ["high-0", "high-1", "high-2", "low"],
            self.web.started,
        )


if __name__ == "__main__":
    unittest.main()
