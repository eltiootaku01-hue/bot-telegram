# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

import pytest

from bot_ia.supervisor.authorization import (
    AuthorizationCheckResult,
    AuthorizationSource,
    AuthorizationStatus,
    WriteAuthorization,
    check_authorization,
)
from bot_ia.supervisor.scope import ChangeBudget, ScopeLock, ScopeOperation
from bot_ia.supervisor.task_contract import Task


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def make_task_and_scope(*, operation=ScopeOperation.WRITE):
    task = Task(
        task_id="TASK-A",
        requester="requester-A",
        task_type="controlled-write",
        scope_id="SCOPE-A",
    )
    scope = ScopeLock.create(
        scope_id="SCOPE-A",
        task_id="TASK-A",
        repository_root=".",
        allowed_paths=("docs/**",),
        allowed_operations=(operation,),
        scope_owner="contract-owner",
        authorization="scope-contract",
        change_budget=ChangeBudget(2, 20, 20, 1, 0),
    )
    return task, scope


def make_authorization(
    *,
    status=AuthorizationStatus.AUTHORIZED,
    task_id="TASK-A",
    scope_id="SCOPE-A",
    requester="requester-A",
    authority="human-admin",
    source=AuthorizationSource.HUMAN,
    operation=ScopeOperation.WRITE,
    target="docs/notes.txt",
    expires_at=NOW + timedelta(minutes=10),
):
    return WriteAuthorization(
        authorization_id="AUTH-A",
        task_id=task_id,
        scope_id=scope_id,
        requester=requester,
        authority=authority,
        source=source,
        operation=operation,
        target=target,
        status=status,
        created_at=NOW,
        expires_at=expires_at,
        reason="explicit contract test",
    )


def trusted(auth):
    return auth.authority == "human-admin"


def test_valid_authorization_is_allowed_without_writing():
    task, scope = make_task_and_scope()
    decision = check_authorization(
        make_authorization(),
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
    )
    assert decision.result is AuthorizationCheckResult.AUTHORIZED


def test_missing_authorization_denies():
    task, scope = make_task_and_scope()
    assert check_authorization(
        None, task, scope, current_time=NOW, authority_validator=trusted
    ).result is AuthorizationCheckResult.DENIED


@pytest.mark.parametrize(
    "status,expected",
    [
        (AuthorizationStatus.DENIED, AuthorizationCheckResult.DENIED),
        (AuthorizationStatus.REVOKED, AuthorizationCheckResult.REVOKED),
        (AuthorizationStatus.EXPIRED, AuthorizationCheckResult.EXPIRED),
        (AuthorizationStatus.REQUESTED, AuthorizationCheckResult.DENIED),
    ],
)
def test_non_authorized_states_fail_closed(status, expected):
    task, scope = make_task_and_scope()
    assert check_authorization(
        make_authorization(status=status),
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
    ).result is expected


def test_expiration_is_checked_at_validation_time():
    task, scope = make_task_and_scope()
    auth = make_authorization(expires_at=NOW + timedelta(seconds=1))
    assert check_authorization(
        auth, task, scope, current_time=NOW, authority_validator=trusted
    ).result is AuthorizationCheckResult.AUTHORIZED
    assert check_authorization(
        auth,
        task,
        scope,
        current_time=NOW + timedelta(seconds=2),
        authority_validator=trusted,
    ).result is AuthorizationCheckResult.EXPIRED


def test_scope_contains_target_and_operation():
    task, scope = make_task_and_scope()
    assert check_authorization(
        make_authorization(),
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
    ).result is AuthorizationCheckResult.AUTHORIZED


@pytest.mark.parametrize(
    "target,operation",
    [
        ("src/private.py", ScopeOperation.WRITE),
        ("docs/notes.txt", ScopeOperation.DELETE),
    ],
)
def test_scope_cannot_be_bypassed(target, operation):
    task, scope = make_task_and_scope(operation=ScopeOperation.WRITE)
    assert check_authorization(
        make_authorization(target=target, operation=operation),
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
    ).result is AuthorizationCheckResult.DENIED


@pytest.mark.parametrize(
    "task_id,scope_id",
    [("TASK-B", "SCOPE-A"), ("TASK-A", "SCOPE-B")],
)
def test_task_and_scope_binding(task_id, scope_id):
    task, scope = make_task_and_scope()
    assert check_authorization(
        make_authorization(task_id=task_id, scope_id=scope_id),
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
    ).result is AuthorizationCheckResult.DENIED


def test_requester_binding():
    task, scope = make_task_and_scope()
    assert check_authorization(
        make_authorization(requester="other"),
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
    ).result is AuthorizationCheckResult.DENIED


def test_missing_authority_is_rejected_at_contract_creation():
    with pytest.raises(ValueError):
        make_authorization(authority="")


def test_self_authorization_is_denied():
    task = Task(
        task_id="TASK-S",
        requester="supervisor",
        task_type="controlled-write",
        scope_id="SCOPE-S",
    )
    scope = ScopeLock.create(
        scope_id="SCOPE-S",
        task_id="TASK-S",
        repository_root=".",
        allowed_paths=("docs/**",),
        allowed_operations=(ScopeOperation.WRITE,),
        scope_owner="supervisor",
        authorization="scope-contract",
    )
    auth = make_authorization(
        task_id="TASK-S",
        scope_id="SCOPE-S",
        requester="supervisor",
        authority="supervisor",
    )
    assert check_authorization(
        auth,
        task,
        scope,
        current_time=NOW,
        authority_validator=lambda item: True,
        supervisor_identity="supervisor",
    ).result is AuthorizationCheckResult.DENIED


def test_supervisor_request_can_be_authorized_by_independent_authority():
    task = Task(
        task_id="TASK-S",
        requester="supervisor",
        task_type="controlled-write",
        scope_id="SCOPE-S",
    )
    scope = ScopeLock.create(
        scope_id="SCOPE-S",
        task_id="TASK-S",
        repository_root=".",
        allowed_paths=("docs/**",),
        allowed_operations=(ScopeOperation.WRITE,),
        scope_owner="supervisor",
        authorization="scope-contract",
    )
    auth = make_authorization(
        task_id="TASK-S",
        scope_id="SCOPE-S",
        requester="supervisor",
        authority="human-admin",
    )
    assert check_authorization(
        auth,
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
        supervisor_identity="supervisor",
    ).result is AuthorizationCheckResult.AUTHORIZED


def test_immutability_and_revocation():
    auth = make_authorization()
    with pytest.raises((AttributeError, TypeError)):
        auth.authority = "other"
    revoked = auth.revoked(reason="human revoked")
    assert auth.status is AuthorizationStatus.AUTHORIZED
    assert revoked.status is AuthorizationStatus.REVOKED
    assert revoked.task_id == auth.task_id
    assert revoked.scope_id == auth.scope_id
    assert revoked.operation is auth.operation
    assert revoked.target == auth.target


def test_authorized_record_requires_independent_authority_validation():
    task, scope = make_task_and_scope()
    auth = make_authorization()
    assert check_authorization(
        auth, task, scope, current_time=NOW
    ).result is AuthorizationCheckResult.DENIED
    assert check_authorization(
        auth,
        task,
        scope,
        current_time=NOW,
        authority_validator=lambda item: False,
    ).result is AuthorizationCheckResult.DENIED


def test_invalid_time_is_not_allowed():
    task, scope = make_task_and_scope()
    naive = datetime(2026, 9, 28, 12, 0)
    assert check_authorization(
        make_authorization(),
        task,
        scope,
        current_time=naive,
        authority_validator=trusted,
    ).result is AuthorizationCheckResult.INVALID


def test_scope_expiration_denies_authorization():
    task, scope = make_task_and_scope()
    scope.expires_at = (NOW - timedelta(seconds=1)).isoformat()
    assert check_authorization(
        make_authorization(),
        task,
        scope,
        current_time=NOW,
        authority_validator=trusted,
    ).result is AuthorizationCheckResult.DENIED


def test_no_physical_write_executor_exists_in_contract():
    import bot_ia.supervisor.authorization as authorization

    assert not hasattr(authorization, "WriteExecutor")
    assert not hasattr(authorization, "FileWriter")
