# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import unittest

from bot_ia.core.task_engine import (
    ResponseDisposition,
    ReturnPolicy,
    TaskEngine,
    TaskState,
    TaskTransitionError,
    TaskWaitReason,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class TaskEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.engine = TaskEngine(now_provider=self.clock.now)

    def test_creation_starts_pending_with_unique_id(self) -> None:
        first = self.engine.create_task("u1", "chat")
        second = self.engine.create_task("u1", "chat")
        self.assertEqual(TaskState.PENDING, first.state)
        self.assertEqual(TaskState.PENDING, second.state)
        self.assertNotEqual(first.task_id, second.task_id)

    def test_start_sets_running_and_started_at(self) -> None:
        task = self.engine.create_task("u1", "chat")
        started = self.engine.start_task(task.task_id)
        self.assertEqual(TaskState.RUNNING, started.state)
        self.assertEqual(self.clock.now(), started.started_at)

    def test_deadline_marks_timeout(self) -> None:
        task = self.engine.create_task(
            "u1",
            "chat",
            deadline=self.clock.now() + timedelta(seconds=30),
        )
        self.engine.start_task(task.task_id)
        self.clock.advance(31)
        self.assertEqual((task.task_id,), self.engine.check_deadlines())
        self.assertEqual(TaskState.TIMED_OUT, self.engine.snapshot(task.task_id).state)

    def test_cancel_moves_running_to_cancelled(self) -> None:
        task = self.engine.create_task("u1", "chat")
        self.engine.start_task(task.task_id)
        cancelling = self.engine.begin_cancellation(task.task_id)
        self.assertEqual(TaskState.CANCELLING, cancelling.state)
        cancelled = self.engine.cancel(task.task_id)
        self.assertEqual(TaskState.CANCELLED, cancelled.state)
        self.assertFalse(self.engine.is_valid(task.task_id))

    def test_late_response_after_cancel_is_discarded(self) -> None:
        task = self.engine.create_task("u1", "chat")
        self.engine.start_task(task.task_id)
        self.engine.cancel(task.task_id)
        self.assertEqual(
            ResponseDisposition.DISCARDED,
            self.engine.validate_response(task.task_id),
        )

    def test_interruption_records_interrupter(self) -> None:
        parent = self.engine.create_task("u1", "main", return_policy=ReturnPolicy.RETURN_IF_VALID)
        child = self.engine.create_task(
            "u1",
            "secondary",
            parent_task_id=parent.task_id,
        )
        self.engine.start_task(parent.task_id)
        self.engine.start_task(child.task_id)
        parent_snapshot = self.engine.snapshot(parent.task_id)
        self.assertEqual(TaskState.INTERRUPTED, parent_snapshot.state)
        self.assertEqual(child.task_id, parent_snapshot.interrupted_by)

    def test_return_to_valid_parent_after_child_completion(self) -> None:
        parent = self.engine.create_task(
            "u1",
            "main",
            return_policy=ReturnPolicy.RETURN_IF_VALID,
            deadline=self.clock.now() + timedelta(minutes=5),
        )
        child = self.engine.create_task(
            "u1",
            "secondary",
            parent_task_id=parent.task_id,
        )
        self.engine.start_task(parent.task_id)
        self.engine.start_task(child.task_id)
        self.engine.complete(child.task_id)
        self.assertEqual(TaskState.RUNNING, self.engine.snapshot(parent.task_id).state)

    def test_expired_parent_is_not_resumed(self) -> None:
        parent = self.engine.create_task(
            "u1",
            "main",
            return_policy=ReturnPolicy.RETURN_IF_VALID,
            deadline=self.clock.now() + timedelta(seconds=10),
        )
        child = self.engine.create_task("u1", "secondary", parent_task_id=parent.task_id)
        self.engine.start_task(parent.task_id)
        self.engine.start_task(child.task_id)
        self.clock.advance(11)
        self.engine.complete(child.task_id)
        self.assertEqual(TaskState.TIMED_OUT, self.engine.snapshot(parent.task_id).state)

    def test_cancelled_parent_is_not_resumed(self) -> None:
        parent = self.engine.create_task(
            "u1",
            "main",
            return_policy=ReturnPolicy.RETURN_IF_VALID,
        )
        child = self.engine.create_task("u1", "secondary", parent_task_id=parent.task_id)
        self.engine.start_task(parent.task_id)
        self.engine.start_task(child.task_id)
        self.engine.cancel(parent.task_id)
        self.engine.complete(child.task_id)
        self.assertEqual(TaskState.CANCELLED, self.engine.snapshot(parent.task_id).state)

    def test_parent_policy_can_discard_parent(self) -> None:
        parent = self.engine.create_task(
            "u1",
            "main",
            return_policy=ReturnPolicy.DISCARD_PARENT,
        )
        child = self.engine.create_task("u1", "secondary", parent_task_id=parent.task_id)
        self.engine.start_task(parent.task_id)
        self.engine.start_task(child.task_id)
        self.engine.complete(child.task_id)
        self.assertEqual(TaskState.DISCARDED, self.engine.snapshot(parent.task_id).state)

    def test_no_return_keeps_parent_interrupted(self) -> None:
        parent = self.engine.create_task(
            "u1",
            "main",
            return_policy=ReturnPolicy.NO_RETURN,
        )
        child = self.engine.create_task("u1", "secondary", parent_task_id=parent.task_id)
        self.engine.start_task(parent.task_id)
        self.engine.start_task(child.task_id)
        self.engine.complete(child.task_id)
        self.assertEqual(TaskState.INTERRUPTED, self.engine.snapshot(parent.task_id).state)

    def test_waiting_reason_is_explicit_and_response_remains_valid(self) -> None:
        task = self.engine.create_task("u1", "web")
        self.engine.start_task(task.task_id)
        self.engine.wait(task.task_id, TaskWaitReason.WEBCHAT)
        snapshot = self.engine.snapshot(task.task_id)
        self.assertEqual(TaskState.WAITING, snapshot.state)
        self.assertEqual(TaskWaitReason.WEBCHAT, snapshot.wait_reason)
        self.assertEqual(ResponseDisposition.ACCEPTED, self.engine.validate_response(task.task_id))

    def test_interrupted_response_is_discarded_until_parent_resumes(self) -> None:
        parent = self.engine.create_task(
            "u1",
            "main",
            return_policy=ReturnPolicy.RETURN_IF_VALID,
        )
        child = self.engine.create_task("u1", "secondary", parent_task_id=parent.task_id)
        self.engine.start_task(parent.task_id)
        self.engine.start_task(child.task_id)
        self.assertEqual(ResponseDisposition.DISCARDED, self.engine.validate_response(parent.task_id))
        self.engine.complete(child.task_id)
        self.assertEqual(ResponseDisposition.ACCEPTED, self.engine.validate_response(parent.task_id))

    def test_task_ids_are_isolated_from_context_text(self) -> None:
        first = self.engine.create_task("u1", "chat", context={"text": "A"})
        second = self.engine.create_task("u1", "chat", context={"text": "A"})
        self.engine.start_task(first.task_id)
        self.engine.start_task(second.task_id)
        self.engine.cancel(first.task_id)
        self.assertEqual(ResponseDisposition.DISCARDED, self.engine.validate_response(first.task_id))
        self.assertEqual(ResponseDisposition.ACCEPTED, self.engine.validate_response(second.task_id))

    def test_duplicate_task_id_is_rejected(self) -> None:
        self.engine.create_task("u1", "chat", task_id="same")
        with self.assertRaises(ValueError):
            self.engine.create_task("u1", "chat", task_id="same")

    def test_invalid_transition_is_rejected(self) -> None:
        task = self.engine.create_task("u1", "chat")
        with self.assertRaises(TaskTransitionError):
            self.engine.complete(task.task_id)


if __name__ == "__main__":
    unittest.main()
