# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

import pytest

from bot_ia.supervisor.scope import ChangeBudget, ScopeLock, ScopeOperation
from bot_ia.supervisor.task_contract import (
    ReturnPolicy, TaskContractStore, TaskPriority, TaskState,
    TaskStateMachine, TaskTransitionError, TaskWaitReason, TERMINAL_STATES,
)

def make_store(): return TaskContractStore()

def make_scope(task_id):
    return ScopeLock.create(
        scope_id="scope-1", task_id=task_id, repository_root=".",
        allowed_paths=("docs/**",), allowed_operations=(ScopeOperation.READ,),
        scope_owner="supervisor", authorization="contract-test",
        change_budget=ChangeBudget(2, 10, 10, 1, 1),
    )

def test_task_creation_and_identity():
    store = make_store()
    task = store.create("user", "audit", task_id="TASK-A", context={"x": 1}, priority=TaskPriority.HIGH)
    assert task.task_id == "TASK-A"
    assert task.priority is TaskPriority.HIGH
    assert task.context == {"x": 1}
    with pytest.raises(ValueError): store.create("user", "audit", task_id="TASK-A")

def test_state_machine():
    assert TaskStateMachine.can_transition(TaskState.PENDING, TaskState.RUNNING)
    assert TaskStateMachine.can_transition(TaskState.RUNNING, TaskState.WAITING)
    assert TaskStateMachine.can_transition(TaskState.RUNNING, TaskState.COMPLETED)
    assert not TaskStateMachine.can_transition(TaskState.COMPLETED, TaskState.RUNNING)
    assert not TaskStateMachine.can_transition(TaskState.CANCELLED, TaskState.WAITING)

def test_wait_reason_required():
    task = make_store().create("user", "audit", task_id="TASK-W")
    TaskStateMachine.transition(task, TaskState.RUNNING)
    with pytest.raises(TaskTransitionError): TaskStateMachine.transition(task, TaskState.WAITING)
    task.wait_reason = TaskWaitReason.WAITING_USER
    TaskStateMachine.transition(task, TaskState.WAITING)
    assert task.wait_reason is TaskWaitReason.WAITING_USER
    TaskStateMachine.transition(task, TaskState.RUNNING)
    assert task.wait_reason is None

def test_all_wait_reasons():
    for reason in TaskWaitReason:
        task = make_store().create("user", "audit", task_id=reason.value)
        TaskStateMachine.transition(task, TaskState.RUNNING)
        task.wait_reason = reason
        TaskStateMachine.transition(task, TaskState.WAITING)
        assert task.state is TaskState.WAITING

def test_parent_child_and_cycle():
    store = make_store()
    parent = store.create("user", "parent", task_id="P")
    child = store.create("user", "child", task_id="C", parent_task_id="P")
    assert child.parent_task_id == parent.task_id
    with pytest.raises(ValueError): store.create("user", "bad", task_id="P2", parent_task_id="P2")
    with pytest.raises(KeyError): store.create("user", "bad", task_id="D", parent_task_id="missing")
    terminal = store.create("user", "terminal", task_id="T")
    terminal.state = TaskState.COMPLETED
    with pytest.raises(ValueError): store.create("user", "bad", task_id="E", parent_task_id="T")
    a = store.create("user", "a", task_id="A")
    b = store.create("user", "b", task_id="B", parent_task_id="A")
    a.parent_task_id = "B"
    with pytest.raises(ValueError): store.create("user", "c", task_id="C", parent_task_id="A")
    assert b.parent_task_id == "A"

def test_return_policies():
    for policy in ReturnPolicy:
        task = make_store().create("user", "child", task_id=policy.value, return_policy=policy)
        assert task.return_policy is policy

def test_late_responses():
    store = make_store()
    store.create("user", "audit", task_id="LIVE")
    assert store.validate_response("LIVE").value == "DISCARDED"
    store.transition("LIVE", TaskState.RUNNING)
    assert store.validate_response("LIVE").value == "ACCEPTED"
    store.transition("LIVE", TaskState.COMPLETED)
    assert store.validate_response("LIVE").value == "DISCARDED"
    assert store.validate_response("UNKNOWN").value == "DISCARDED"
    with pytest.raises(TaskTransitionError): store.attach_result("LIVE", "late")

def test_terminal_states():
    for state in TERMINAL_STATES:
        assert not TaskStateMachine.can_transition(state, TaskState.RUNNING)
        assert not TaskStateMachine.can_transition(state, TaskState.WAITING)

def test_scope_reference():
    store = make_store()
    task = store.create("user", "audit", task_id="TASK-S", scope_lock=make_scope("TASK-S"))
    assert task.scope_id == "scope-1"
    with pytest.raises(ValueError): store.create("user", "audit", task_id="TASK-BAD", scope_lock=make_scope("OTHER"))
    with pytest.raises(ValueError): store.create("user", "audit", task_id="TASK-MISSING-SCOPE", scope_id="missing")

def test_deadline_and_timeout_policy():
    deadline = datetime.now(timezone.utc) + timedelta(minutes=1)
    task = make_store().create("user", "audit", task_id="TASK-T", deadline=deadline, timeout_policy="mark_timed_out")
    assert task.deadline == deadline
    assert task.timeout_policy == "mark_timed_out"
