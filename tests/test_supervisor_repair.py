# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

import pytest

from bot_ia.supervisor.authorization import AuthorizationSource, WriteAuthorization
from bot_ia.supervisor.repair import (
    Hypothesis, HypothesisStatus, RepairAttempt, RepairAttemptLedger,
    RepairAttemptStatus, RepairBudget, RepairProposal, RepairStatus,
    VerificationResult, VerificationStatus, repair_audit_event,
)
from bot_ia.supervisor.scope import ChangeBudget, ScopeLock, ScopeOperation
from bot_ia.supervisor.task_contract import Task

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def make_task_scope():
    task = Task(task_id="TASK-R", requester="requester", task_type="repair-contract", scope_id="SCOPE-R")
    scope = ScopeLock.create(
        scope_id="SCOPE-R", task_id="TASK-R", repository_root=".",
        allowed_paths=("docs/**",), allowed_operations=(ScopeOperation.WRITE,),
        scope_owner="owner", authorization="scope-contract",
        change_budget=ChangeBudget(3, 20, 20, 0, 3),
    )
    return task, scope


def make_hypothesis(**kwargs):
    values = dict(
        statement="The Windows failure may come from a POSIX-only call.",
        task_id="TASK-R", scope_id="SCOPE-R", created_by="supervisor",
        reason="documented failure requires a testable explanation", created_at=NOW,
    )
    values.update(kwargs)
    return Hypothesis.create(**values)


def make_budget(max_attempts=3):
    return RepairBudget(
        max_attempts=max_attempts, max_files=2, max_lines=20, max_changes=2,
        max_duration_seconds=60, allowed_operations=frozenset({ScopeOperation.WRITE}),
    )


def make_proposal(*, authorization_id=None, budget=None, target="docs/notes.txt"):
    task, scope = make_task_scope()
    return RepairProposal.propose(
        hypothesis=make_hypothesis(), task=task, scope=scope,
        description="replace the mechanism if the hypothesis is confirmed",
        target=target, operation=ScopeOperation.WRITE,
        expected_effect="remove the observed Windows failure",
        risk="may alter repository behavior", evidence_ids=("ev-before",),
        authorization_id=authorization_id, budget=budget or make_budget(), created_at=NOW,
    )


def test_hypothesis_creation_and_identity():
    hypothesis = make_hypothesis(hypothesis_id="H1", claim_ids=("C1",))
    assert hypothesis.hypothesis_id == "H1"
    assert hypothesis.status is HypothesisStatus.PROPOSED
    assert hypothesis.confidence.value == "UNKNOWN"
    assert hypothesis.claim_ids == ("C1",)
    assert hypothesis.created_at == NOW
    assert hypothesis.updated_at == NOW


@pytest.mark.parametrize(
    "current,target",
    [
        (HypothesisStatus.PROPOSED, HypothesisStatus.SUPPORTED),
        (HypothesisStatus.SUPPORTED, HypothesisStatus.TESTING),
        (HypothesisStatus.REFUTED, HypothesisStatus.TESTING),
        (HypothesisStatus.CLOSED, HypothesisStatus.TESTING),
    ],
)
def test_invalid_hypothesis_transitions_fail_closed(current, target):
    hypothesis = make_hypothesis()
    if current is HypothesisStatus.SUPPORTED:
        hypothesis = hypothesis.transition(HypothesisStatus.TESTING, reason="set test state")
        hypothesis = hypothesis.record_test(
            verification=VerificationStatus.PASS,
            evidence_ids=("ev-support",),
            reason="set supported state",
        )
    elif current is HypothesisStatus.REFUTED:
        hypothesis = hypothesis.transition(HypothesisStatus.TESTING, reason="set test state")
        hypothesis = hypothesis.record_test(
            verification=VerificationStatus.FAIL,
            evidence_ids=("ev-refute",),
            reason="set refuted state",
        )
    elif current is HypothesisStatus.CLOSED:
        hypothesis = hypothesis.transition(HypothesisStatus.CLOSED, reason="set closed state")
    with pytest.raises(ValueError):
        hypothesis.transition(target, reason="invalid transition")


def test_hypothesis_support_and_refutation_are_distinct():
    hypothesis = make_hypothesis().transition(HypothesisStatus.TESTING, reason="begin deterministic test")
    supported = hypothesis.record_test(
        verification=VerificationStatus.PASS, evidence_ids=("ev-support",), reason="test passed"
    )
    assert supported.status is HypothesisStatus.SUPPORTED
    assert supported.supporting_evidence_ids == ("ev-support",)
    assert supported.refutation_evidence_ids == ()
    refuted = hypothesis.record_test(
        verification=VerificationStatus.FAIL, evidence_ids=("ev-refute",), reason="test failed"
    )
    assert refuted.status is HypothesisStatus.REFUTED
    assert refuted.refutation_evidence_ids == ("ev-refute",)
    assert refuted.supporting_evidence_ids == ()


def test_hypothesis_inconclusive_and_blocked_do_not_become_fact():
    hypothesis = make_hypothesis().transition(HypothesisStatus.TESTING, reason="start test")
    inconclusive = hypothesis.record_test(
        verification=VerificationStatus.INCONCLUSIVE, evidence_ids=("ev-unknown",),
        reason="evidence is insufficient",
    )
    assert inconclusive.status is HypothesisStatus.INCONCLUSIVE
    assert inconclusive.confidence.value != "VERIFIED"
    blocked = hypothesis.record_test(
        verification=VerificationStatus.BLOCKED, evidence_ids=("ev-blocked",),
        reason="required information is unavailable",
    )
    assert blocked.status is HypothesisStatus.BLOCKED
    assert blocked.evidence_ids == ("ev-blocked",)


def test_hypothesis_rejects_verified_confidence():
    with pytest.raises(ValueError):
        make_hypothesis(confidence="VERIFIED")


def test_parent_hypothesis_is_supported_without_being_a_fact():
    parent = make_hypothesis(hypothesis_id="H-PARENT")
    child = make_hypothesis(parent_hypothesis_id=parent.hypothesis_id)
    assert child.parent_hypothesis_id == "H-PARENT"
    assert child.status is HypothesisStatus.PROPOSED


def test_hypothesis_evidence_requires_explicit_role():
    with pytest.raises(ValueError):
        make_hypothesis().add_evidence(("ev-1",))


def test_repair_proposal_binds_hypothesis_task_scope_and_operation():
    proposal = make_proposal()
    assert proposal.status is RepairStatus.PROPOSED
    assert proposal.hypothesis_id
    assert proposal.task_id == "TASK-R"
    assert proposal.scope_id == "SCOPE-R"
    assert proposal.operation is ScopeOperation.WRITE


def test_proposal_outside_scope_is_blocked():
    assert make_proposal(target="src/private.py").status is RepairStatus.BLOCKED


def test_proposal_budget_operation_ceiling_is_blocked():
    budget = RepairBudget(
        max_attempts=3, max_files=2, max_lines=20, max_changes=2,
        max_duration_seconds=60, allowed_operations=frozenset({ScopeOperation.READ}),
    )
    assert make_proposal(budget=budget).status is RepairStatus.BLOCKED


def test_proposal_without_authorization_cannot_execute():
    task, scope = make_task_scope()
    approved = make_proposal().transition(RepairStatus.APPROVED)
    assert approved.execution_authorized(
        task=task, scope=scope, authorization=None,
        authority_validator=lambda auth: True, current_time=NOW,
    ) is False


def test_approval_is_not_execution():
    assert make_proposal().transition(RepairStatus.APPROVED).status is RepairStatus.APPROVED


def test_authorization_is_checked_against_proposal_binding():
    task, scope = make_task_scope()
    proposal = make_proposal(authorization_id="AUTH-1").transition(RepairStatus.APPROVED)
    auth = WriteAuthorization(
        authorization_id="AUTH-2", task_id=task.task_id, scope_id=scope.scope_id,
        requester=task.requester, authority="human-admin", source=AuthorizationSource.HUMAN,
        operation=ScopeOperation.WRITE, target="docs/notes.txt", status="AUTHORIZED",
        created_at=NOW, expires_at=NOW + timedelta(minutes=5),
    )
    assert proposal.execution_authorized(
        task=task, scope=scope, authorization=auth,
        authority_validator=lambda item: True, current_time=NOW,
    ) is False


def test_attempt_rejects_authorization_not_bound_to_proposal():
    proposal = make_proposal().transition(RepairStatus.APPROVED)
    blocked = RepairAttempt.start(
        repair=proposal, attempt_number=1, evidence_before=("ev-before",),
        authorization_id="AUTH-ARBITRARY", budget=make_budget(), started_at=NOW,
    )
    assert blocked.status is RepairAttemptStatus.BLOCKED
    assert "matching authorization" in (blocked.failure_reason or "")


def test_attempt_requires_approved_proposal_and_authorization():
    blocked = RepairAttempt.start(
        repair=make_proposal(), attempt_number=1, evidence_before=("ev-before",),
        authorization_id=None, budget=make_budget(), started_at=NOW,
    )
    assert blocked.status is RepairAttemptStatus.BLOCKED
    assert blocked.failure_reason


def test_attempt_budget_exhaustion_is_blocked():
    proposal = make_proposal(authorization_id="AUTH-1").transition(RepairStatus.APPROVED)
    attempt = RepairAttempt.start(
        repair=proposal, attempt_number=4, evidence_before=("ev-before",),
        authorization_id="AUTH-1", budget=make_budget(max_attempts=3), started_at=NOW,
    )
    assert attempt.status is RepairAttemptStatus.BLOCKED
    assert "budget" in (attempt.failure_reason or "")


def test_attempt_history_is_append_only_and_sequential():
    proposal = make_proposal(authorization_id="AUTH-1").transition(RepairStatus.APPROVED)
    ledger = RepairAttemptLedger()
    first = RepairAttempt.start(
        repair=proposal, attempt_number=1, evidence_before=("ev-before-1",),
        authorization_id="AUTH-1", budget=make_budget(), started_at=NOW,
    ).finish(
        status=RepairAttemptStatus.FAILED, evidence_after=("ev-after-1",),
        changed_files=("docs/notes.txt",), changed_lines=4,
        failure_reason="verification failed", rollback_required=True,
        finished_at=NOW + timedelta(seconds=5), budget=make_budget(),
    )
    ledger.add(first)
    second = RepairAttempt.start(
        repair=proposal, attempt_number=2, evidence_before=("ev-before-2",),
        authorization_id="AUTH-1", budget=make_budget(), started_at=NOW + timedelta(seconds=6),
    )
    ledger.add(second)
    assert ledger.next_attempt_number(proposal.repair_id) == 3
    assert [item.attempt_number for item in ledger.history(proposal.repair_id)] == [1, 2]
    with pytest.raises(ValueError):
        ledger.add(first)
    with pytest.raises(ValueError):
        ledger.add(RepairAttempt.start(
            repair=proposal, attempt_number=4, evidence_before=(),
            authorization_id="AUTH-1", budget=make_budget(), started_at=NOW + timedelta(seconds=7),
        ))


def test_budget_limits_files_lines_changes_and_duration():
    budget = make_budget()
    assert budget.check(attempt_number=1, files_changed=2, lines_changed=20, changes=2, duration_seconds=60)
    assert not budget.check(attempt_number=1, files_changed=3, lines_changed=20, changes=2, duration_seconds=60)
    assert not budget.check(attempt_number=1, files_changed=2, lines_changed=21, changes=2, duration_seconds=60)
    assert not budget.check(attempt_number=1, files_changed=2, lines_changed=20, changes=3, duration_seconds=60)
    assert not budget.check(attempt_number=1, files_changed=2, lines_changed=20, changes=2, duration_seconds=61)
    assert not budget.check(attempt_number=4, files_changed=0, lines_changed=0, changes=0, duration_seconds=0)


def test_changed_lines_can_remain_unknown_without_inventing_a_value():
    proposal = make_proposal(authorization_id="AUTH-1").transition(RepairStatus.APPROVED)
    attempt = RepairAttempt.start(
        repair=proposal, attempt_number=1, evidence_before=("ev-before",),
        authorization_id="AUTH-1", budget=make_budget(), started_at=NOW,
    ).finish(
        status=RepairAttemptStatus.SUCCEEDED, evidence_after=("ev-after",),
        changed_files=("docs/notes.txt",), changed_lines=None,
        finished_at=NOW + timedelta(seconds=1), budget=make_budget(),
    )
    assert attempt.changed_lines is None


def test_verification_requires_evidence_and_preserves_result():
    proposal = make_proposal(authorization_id="AUTH-1")
    with pytest.raises(ValueError):
        VerificationResult.create(
            repair_id=proposal.repair_id, attempt_id="attempt-1",
            status=VerificationStatus.PASS, evidence_ids=(), reason="no evidence",
        )
    result = VerificationResult.create(
        repair_id=proposal.repair_id, attempt_id="attempt-1",
        status=VerificationStatus.PASS, evidence_ids=("ev-verify",),
        reason="tests passed", created_at=NOW,
    )
    assert result.status is VerificationStatus.PASS
    assert result.evidence_ids == ("ev-verify",)


def test_failed_repair_does_not_delete_history():
    proposal = make_proposal(authorization_id="AUTH-1").transition(RepairStatus.APPROVED)
    ledger = RepairAttemptLedger()
    attempt = RepairAttempt.start(
        repair=proposal, attempt_number=1, evidence_before=("ev-before",),
        authorization_id="AUTH-1", budget=make_budget(), started_at=NOW,
    ).finish(
        status=RepairAttemptStatus.FAILED, evidence_after=("ev-after",),
        failure_reason="failed verification", finished_at=NOW + timedelta(seconds=1),
        budget=make_budget(),
    )
    ledger.add(attempt)
    assert len(ledger.history(proposal.repair_id)) == 1
    assert ledger.history(proposal.repair_id)[0].status is RepairAttemptStatus.FAILED


def test_rollback_is_only_represented():
    proposal = make_proposal(authorization_id="AUTH-1").transition(RepairStatus.APPROVED)
    attempt = RepairAttempt.start(
        repair=proposal, attempt_number=1, evidence_before=("ev-before",),
        authorization_id="AUTH-1", budget=make_budget(), started_at=NOW,
    ).finish(
        status=RepairAttemptStatus.FAILED, evidence_after=("ev-after",),
        failure_reason="failure requires review", rollback_required=True,
        finished_at=NOW + timedelta(seconds=1), budget=make_budget(),
    )
    assert attempt.rollback_required is True


def test_audit_events_reuse_existing_audit_model():
    event = repair_audit_event(
        operation="repair_attempt_finished", repair_id="R1",
        hypothesis_id="H1", task_id="TASK-R", result="FAILED",
    )
    assert event.operation == "repair_attempt_finished"
    assert event.task_id == "TASK-R"
    assert event.metadata["repair_id"] == "R1"
    assert event.metadata["hypothesis_id"] == "H1"


def test_contract_contains_no_physical_writer():
    import bot_ia.supervisor.repair as repair
    assert not hasattr(repair, "WriteExecutor")
    assert not hasattr(repair, "FileWriter")
    assert not hasattr(repair, "GitWriter")
