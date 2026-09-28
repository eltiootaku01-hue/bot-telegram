# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

import pytest

from bot_ia.core.task_engine import TaskEngine, TaskState, TaskWaitReason
from bot_ia.core.task_scheduler import TaskRoute, TaskScheduler
from bot_ia.supervisor.boundary import BoundaryDecision, SupervisorCommand, TaskEngineBoundary
from bot_ia.supervisor.models import EvidenceStatus, EvidenceType
from bot_ia.supervisor.runtime_observation import RuntimeObservation


class ProbeExecutor:
    def __init__(self):
        self.submitted = []
        self.cancelled = []

    def submit(self, task):
        self.submitted.append(task.task_id)

    def cancel(self, task_id):
        self.cancelled.append(task_id)


def make_runtime():
    engine = TaskEngine()
    scheduler = TaskScheduler(engine)
    executor = ProbeExecutor()
    scheduler.register_executor(TaskRoute.LOCAL, executor)
    boundary = TaskEngineBoundary(engine, scheduler)
    observer = RuntimeObservation(boundary)
    return engine, scheduler, executor, boundary, observer


def create_task(engine, task_id="TASK-RUNTIME", **kwargs):
    return engine.create_task(
        requester="runtime-test",
        task_type="controlled-test",
        task_id=task_id,
        **kwargs,
    )


def state_of(observer, task_id):
    evidence = observer.task(task_id, scenario="state")
    return evidence.metadata["snapshot"]["state"]


def test_runtime_normal_lifecycle_uses_real_task_engine_and_scheduler():
    engine, scheduler, executor, _, observer = make_runtime()
    create_task(engine)

    pending = observer.task("TASK-RUNTIME", scenario="normal-pending")
    assert pending.result is EvidenceStatus.OBSERVED
    assert pending.type is EvidenceType.RUNTIME_EVIDENCE
    assert pending.metadata["snapshot"]["state"] == "PENDING"

    scheduler.schedule("TASK-RUNTIME", TaskRoute.LOCAL)
    scheduler_evidence = observer.scheduler(scenario="normal-scheduled")
    assert scheduler_evidence.metadata["snapshot"]["pending_task_ids"] == ("TASK-RUNTIME",)

    assert scheduler.dispatch() == ("TASK-RUNTIME",)
    running = observer.task("TASK-RUNTIME", scenario="normal-running")
    assert running.metadata["snapshot"]["state"] == "RUNNING"
    assert executor.submitted == ["TASK-RUNTIME"]

    engine.complete("TASK-RUNTIME")
    scheduler.execution_finished("TASK-RUNTIME")
    completed = observer.task("TASK-RUNTIME", scenario="normal-completed")
    assert completed.metadata["snapshot"]["state"] == "COMPLETED"
    assert completed.metadata["snapshot"]["task_id"] == "TASK-RUNTIME"


def test_wait_resume_lifecycle_is_observed_without_observer_mutation():
    engine, scheduler, _, _, observer = make_runtime()
    create_task(engine, "TASK-WAIT")
    scheduler.schedule("TASK-WAIT", TaskRoute.LOCAL)
    scheduler.dispatch()

    before_wait = observer.task("TASK-WAIT", scenario="before-wait")
    scheduler.wait("TASK-WAIT", TaskWaitReason.TIMER)
    waiting = observer.task("TASK-WAIT", scenario="waiting")
    assert waiting.metadata["snapshot"]["state"] == "WAITING"
    assert waiting.metadata["snapshot"]["wait_reason"] == "WAITING_TIMER"

    scheduler.wake("TASK-WAIT")
    running = observer.task("TASK-WAIT", scenario="resumed")
    assert running.metadata["snapshot"]["state"] == "RUNNING"
    transition = observer.transition(
        before_wait, running, transition_source="TaskScheduler.wake", scenario="wait-resume"
    )
    assert transition.result is EvidenceStatus.TESTED
    assert transition.metadata["task_id"] == "TASK-WAIT"


def test_cancellation_is_owned_by_scheduler_and_engine():
    engine, scheduler, executor, _, observer = make_runtime()
    create_task(engine, "TASK-CANCEL")
    scheduler.schedule("TASK-CANCEL", TaskRoute.LOCAL)
    scheduler.dispatch()

    result = scheduler.cancel("TASK-CANCEL")
    assert result.state is TaskState.CANCELLED
    assert executor.cancelled == ["TASK-CANCEL"]
    assert state_of(observer, "TASK-CANCEL") == "CANCELLED"


def test_failure_is_reported_from_executor_boundary():
    engine, scheduler, _, _, observer = make_runtime()
    create_task(engine, "TASK-FAIL")
    scheduler.schedule("TASK-FAIL", TaskRoute.LOCAL)
    scheduler.dispatch()

    result = scheduler.fail_from_executor("TASK-FAIL")
    assert result.state is TaskState.FAILED
    evidence = observer.task("TASK-FAIL", scenario="failure")
    assert evidence.metadata["snapshot"]["state"] == "FAILED"


def test_timeout_is_observed_from_real_scheduler_deadline_check():
    clock = [datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)]
    engine = TaskEngine(now_provider=lambda: clock[0])
    scheduler = TaskScheduler(engine)
    scheduler.register_executor(TaskRoute.LOCAL, ProbeExecutor())
    boundary = TaskEngineBoundary(engine, scheduler)
    observer = RuntimeObservation(boundary)

    create_task(
        engine,
        "TASK-TIMEOUT",
        deadline=clock[0] + timedelta(seconds=1),
    )
    scheduler.schedule("TASK-TIMEOUT", TaskRoute.LOCAL)
    clock[0] += timedelta(seconds=2)
    assert scheduler.dispatch() == ()
    evidence = observer.task("TASK-TIMEOUT", scenario="timeout")
    assert evidence.metadata["snapshot"]["state"] == "TIMED_OUT"


def test_unknown_task_is_unknown_evidence_and_boundary_is_blocked():
    _, _, _, boundary, observer = make_runtime()
    evidence = observer.task("DOES-NOT-EXIST", scenario="unknown")
    assert evidence.result is EvidenceStatus.UNKNOWN
    assert evidence.metadata["reason"] == "unknown task_id"

    decision = boundary.validate_request("DOES-NOT-EXIST", SupervisorCommand.REQUEST)
    assert decision.decision is BoundaryDecision.BLOCKED


def test_terminal_task_rejects_operational_request():
    engine, _, _, boundary, observer = make_runtime()
    create_task(engine, "TASK-TERMINAL")
    engine.start_task("TASK-TERMINAL")
    engine.complete("TASK-TERMINAL")

    evidence = observer.task("TASK-TERMINAL", scenario="terminal")
    assert evidence.metadata["snapshot"]["state"] == "COMPLETED"
    decision = boundary.validate_request("TASK-TERMINAL", SupervisorCommand.REQUEST)
    assert decision.decision is BoundaryDecision.BLOCKED


def test_observation_is_read_only_for_task_and_scheduler():
    engine, scheduler, _, _, observer = make_runtime()
    create_task(engine, "TASK-READONLY")
    scheduler.schedule("TASK-READONLY", TaskRoute.LOCAL)

    task_before = engine.snapshot("TASK-READONLY")
    scheduler_before = observer.scheduler(scenario="before")
    task_evidence = observer.task("TASK-READONLY", scenario="observation")
    scheduler_after = observer.scheduler(scenario="after")
    task_after = engine.snapshot("TASK-READONLY")

    assert task_before == task_after
    assert scheduler_before.metadata["snapshot"] == scheduler_after.metadata["snapshot"]
    assert task_evidence.result is EvidenceStatus.OBSERVED


def test_scheduler_observation_does_not_select_or_dispatch():
    engine, scheduler, executor, _, observer = make_runtime()
    create_task(engine, "TASK-SCHEDULER")
    scheduler.schedule("TASK-SCHEDULER", TaskRoute.LOCAL)

    before = observer.scheduler(scenario="before")
    task_before = engine.snapshot("TASK-SCHEDULER")
    after = observer.scheduler(scenario="after")

    assert before.metadata["snapshot"] == after.metadata["snapshot"]
    assert after.metadata["snapshot"]["pending_task_ids"] == ("TASK-SCHEDULER",)
    assert after.metadata["snapshot"]["active_task_ids"] == ()
    assert executor.submitted == []
    assert engine.snapshot("TASK-SCHEDULER") == task_before


def test_parent_child_identity_is_preserved_in_runtime():
    engine, scheduler, _, _, observer = make_runtime()
    create_task(engine, "PARENT")
    create_task(engine, "CHILD", parent_task_id="PARENT")
    scheduler.schedule("CHILD", TaskRoute.LOCAL)

    evidence = observer.task("CHILD", scenario="parent-child")
    snapshot = evidence.metadata["snapshot"]
    assert snapshot["task_id"] == "CHILD"
    assert snapshot["parent_task_id"] == "PARENT"


def test_task_id_mismatch_in_runtime_transition_is_blocked():
    _, _, _, _, observer = make_runtime()
    first = observer.task("UNKNOWN-A", scenario="before")
    second = observer.task("UNKNOWN-B", scenario="after")
    result = observer.transition(
        first, second, transition_source="unknown", scenario="mismatch"
    )
    assert result.result is EvidenceStatus.BLOCKED
    assert "task_id mismatch" in result.metadata["reason"]


def test_observation_timestamp_must_be_timezone_aware():
    _, _, _, _, observer = make_runtime()
    with pytest.raises(ValueError):
        observer.task(
            "UNKNOWN",
            scenario="naive-clock",
            observed_at=datetime(2026, 9, 28, 12, 0),
        )
