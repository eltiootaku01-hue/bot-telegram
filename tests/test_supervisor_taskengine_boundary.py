# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot_ia.core.task_engine import TaskEngine, TaskState
from bot_ia.core.task_scheduler import TaskScheduler
from bot_ia.supervisor.authorization import AuthorizationSource, AuthorizationStatus, WriteAuthorization
from bot_ia.supervisor.scope import ChangeBudget, ScopeLock, ScopeOperation
from bot_ia.supervisor.boundary import BoundaryDecision, SupervisorCommand, TaskEngineBoundary


def make_scope(task_id: str, operation: ScopeOperation = ScopeOperation.READ):
    return ScopeLock.create(
        scope_id="scope-boundary",
        task_id=task_id,
        repository_root=Path("."),
        allowed_paths=("docs/**",),
        allowed_operations=(operation,),
        scope_owner="supervisor",
        authorization="contract-test",
        change_budget=ChangeBudget(1, 10, 10, 1, 1),
    )


def make_write_authorization(task_id: str, requester: str, target: str):
    now = datetime.now(timezone.utc)
    return WriteAuthorization(
        authorization_id="AUTH-BOUNDARY",
        task_id=task_id,
        scope_id="scope-boundary",
        requester=requester,
        authority="human-admin",
        source=AuthorizationSource.HUMAN,
        operation=ScopeOperation.WRITE,
        target=target,
        status=AuthorizationStatus.AUTHORIZED,
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def test_observe_is_read_only_and_preserves_task_identity():
    engine = TaskEngine()
    task = engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    before = engine.snapshot("TASK-1")
    observed = boundary.observe_task("TASK-1")
    after = engine.snapshot("TASK-1")
    assert observed.task_id == task.task_id
    assert observed.state is TaskState.PENDING
    assert before == after


def test_task_id_mismatch_is_blocked():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    result = boundary.validate_request("TASK-UNKNOWN", SupervisorCommand.REQUEST)
    assert result.decision is BoundaryDecision.BLOCKED


def test_unknown_command_is_fail_closed():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    result = boundary.validate_request("TASK-1", "UNKNOWN")
    assert result.decision is BoundaryDecision.UNKNOWN


def test_terminal_task_cannot_receive_operational_request():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    engine.start_task("TASK-1")
    engine.complete("TASK-1")
    boundary = TaskEngineBoundary(engine)
    result = boundary.validate_request("TASK-1", SupervisorCommand.REQUEST)
    assert result.decision is BoundaryDecision.BLOCKED


def test_scope_mismatch_is_blocked():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    scope = make_scope("OTHER")
    result = boundary.validate_request(
        "TASK-1", SupervisorCommand.REQUEST,
        scope=scope, operation=ScopeOperation.READ, target="docs/a.txt",
    )
    assert result.decision is BoundaryDecision.BLOCKED


def test_write_request_without_authorization_is_denied():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    scope = make_scope("TASK-1", ScopeOperation.WRITE)
    result = boundary.validate_request(
        "TASK-1", SupervisorCommand.REQUEST,
        scope=scope, operation=ScopeOperation.WRITE, target="docs/a.txt",
    )
    assert result.decision is BoundaryDecision.DENIED


def test_authorization_binding_is_checked_without_execution():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    scope = make_scope("TASK-1", ScopeOperation.WRITE)
    authorization = make_write_authorization("TASK-1", "user", "docs/a.txt")
    result = boundary.validate_request(
        "TASK-1", SupervisorCommand.REQUEST,
        scope=scope, authorization=authorization,
        operation=ScopeOperation.WRITE, target="docs/a.txt",
        authority_validator=lambda _: True,
    )
    assert result.decision is BoundaryDecision.ALLOWED
    assert engine.snapshot("TASK-1").state is TaskState.PENDING


def test_authorization_task_mismatch_is_denied():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    scope = make_scope("TASK-1", ScopeOperation.WRITE)
    authorization = make_write_authorization("OTHER", "user", "docs/a.txt")
    result = boundary.validate_request(
        "TASK-1", SupervisorCommand.REQUEST,
        scope=scope, authorization=authorization,
        operation=ScopeOperation.WRITE, target="docs/a.txt",
        authority_validator=lambda _: True,
    )
    assert result.decision is BoundaryDecision.BLOCKED


def test_validated_request_does_not_execute_task():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    boundary = TaskEngineBoundary(engine)
    scope = make_scope("TASK-1", ScopeOperation.READ)
    result = boundary.validate_request(
        "TASK-1", SupervisorCommand.VERIFY,
        scope=scope, operation=ScopeOperation.READ, target="docs/a.txt",
    )
    assert result.decision is BoundaryDecision.DENIED
    assert engine.snapshot("TASK-1").state is TaskState.PENDING


def test_scheduler_observation_does_not_select_or_dispatch():
    engine = TaskEngine()
    engine.create_task("user", "audit", task_id="TASK-1")
    scheduler = TaskScheduler(engine)
    boundary = TaskEngineBoundary(engine, scheduler)
    observed = boundary.observe_scheduler()
    assert observed.pending_task_ids == ()
    assert observed.active_task_ids == ()
    assert engine.snapshot("TASK-1").state is TaskState.PENDING


def test_scheduler_must_share_same_task_engine():
    engine = TaskEngine()
    other = TaskEngine()
    scheduler = TaskScheduler(other)
    try:
        TaskEngineBoundary(engine, scheduler)
    except ValueError:
        pass
    else:
        raise AssertionError("boundary accepted a scheduler owned by another TaskEngine")


def test_parent_child_identity_is_observed_without_reimplementation():
    engine = TaskEngine()
    parent = engine.create_task("user", "parent", task_id="PARENT")
    child = engine.create_task("user", "child", task_id="CHILD", parent_task_id=parent.task_id)
    boundary = TaskEngineBoundary(engine)
    observed = boundary.observe_task(child.task_id)
    assert observed.parent_task_id == parent.task_id
