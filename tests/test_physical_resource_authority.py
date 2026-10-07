# -*- coding: utf-8 -*-
"""Contract tests for the isolated Physical WebChat Resource Authority."""

import threading
import unittest

from bot_ia.core.physical_resource_authority import (
    PhysicalReleaseEvidenceType,
    PhysicalResourceClaimError,
    PhysicalResourceIdentityError,
    PhysicalResourceOwnershipError,
    PhysicalResourceState,
    PhysicalResourceStateError,
    PhysicalWebChatResourceAuthority,
    _issue_physical_release_evidence,
)


class PhysicalWebChatResourceAuthorityTests(unittest.TestCase):
    def _termination_evidence(
        self,
        claim,
        *,
        operation_id=None,
        observation="controlled termination",
    ):
        return _issue_physical_release_evidence(
            provider=self.resource.provider,
            evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
            physical_resource_id=claim.physical_resource_id,
            claim_id=claim.claim_id,
            execution_generation=claim.execution_generation,
            operation_id=operation_id,
            observation=observation,
        )

    def _sanitization_evidence(
        self,
        snapshot,
        *,
        observation="controlled sanitization",
    ):
        return _issue_physical_release_evidence(
            provider=self.resource.provider,
            evidence_type=PhysicalReleaseEvidenceType.SANITIZATION,
            physical_resource_id=snapshot.physical_resource_id,
            claim_id=snapshot.claim_id,
            execution_generation=snapshot.execution_generation,
            operation_id=snapshot.operation_id,
            observation=observation,
        )
    def setUp(self) -> None:
        self.authority = PhysicalWebChatResourceAuthority()
        self.resource = self.authority.resolve_resource(
            " Gemini ",
            "Account@Example.com",
            " Session-1 ",
            " /chat/cari ",
        )

    def test_t01_identity_determinism(self) -> None:
        other = self.authority.resolve_resource(
            "gemini",
            "account@example.com",
            "session-1",
            "/chat/cari",
        )
        self.assertEqual(self.resource.physical_resource_id, other.physical_resource_id)

    def test_t02_different_account_has_different_resource(self) -> None:
        other = self.authority.resolve_resource(
            "gemini",
            "other@example.com",
            "session-1",
            "/chat/cari",
        )
        self.assertNotEqual(self.resource.physical_resource_id, other.physical_resource_id)

    def test_t03_different_surface_has_different_resource(self) -> None:
        other = self.authority.resolve_resource(
            "gemini",
            "account@example.com",
            "session-1",
            "/chat/cami",
        )
        self.assertNotEqual(self.resource.physical_resource_id, other.physical_resource_id)

    def test_t04_unresolved_identity_is_rejected(self) -> None:
        with self.assertRaises(PhysicalResourceIdentityError):
            self.authority.resolve_resource(
                "gemini",
                "account@example.com",
                "",
                "/chat/cari",
            )

    def test_t05_one_owner_invariant(self) -> None:
        first = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        with self.assertRaises(PhysicalResourceClaimError):
            self.authority.claim(self.resource.physical_resource_id, "owner-b")
        current = self.authority.snapshot(self.resource.physical_resource_id)
        self.assertEqual("owner-a", current.owner)
        self.assertEqual(first.claim_id, current.claim_id)

    def test_t06_release_returns_available(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        released = self.authority.release(claim)
        self.assertEqual(PhysicalResourceState.AVAILABLE, released.state)
        self.assertIsNone(released.owner)

    def test_t07_stale_release_cannot_release_new_owner(self) -> None:
        first = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.release(first)
        second = self.authority.claim(self.resource.physical_resource_id, "owner-b")
        with self.assertRaises(PhysicalResourceOwnershipError):
            self.authority.release(first)
        current = self.authority.snapshot(self.resource.physical_resource_id)
        self.assertEqual(second.claim_id, current.claim_id)
        self.assertEqual("owner-b", current.owner)

    def test_t08_generation_changes_after_release_and_reclaim(self) -> None:
        first = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.release(first)
        second = self.authority.claim(self.resource.physical_resource_id, "owner-b")
        self.assertNotEqual(
            first.execution_generation,
            second.execution_generation,
        )

    def test_t09_late_callback_is_rejected(self) -> None:
        first = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(first, operation_id="op-1")
        self.authority.release(
            first,
            evidence=self._termination_evidence(
                first,
                operation_id="op-1",
            ),
        )
        second = self.authority.claim(self.resource.physical_resource_id, "owner-b")
        self.authority.begin_execution(second, operation_id="op-2")
        self.assertFalse(
            self.authority.validate_execution(
                self.resource.physical_resource_id,
                first.claim_id,
                first.execution_generation,
                operation_id="op-1",
            )
        )
        current = self.authority.snapshot(self.resource.physical_resource_id)
        self.assertEqual(second.claim_id, current.claim_id)
        self.assertEqual("op-2", current.operation_id)

    def test_t10_quarantine(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(claim, backend="qweb")
        quarantined = self.authority.quarantine(
            claim,
            "TERMINATION_UNCONFIRMED",
            evidence="no termination evidence",
        )
        self.assertEqual(PhysicalResourceState.QUARANTINED, quarantined.state)
        self.assertEqual("TERMINATION_UNCONFIRMED", quarantined.quarantine_reason)
        self.assertEqual("no termination evidence", quarantined.last_error)

    def test_t11_quarantine_does_not_auto_release(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.quarantine(claim, "UNKNOWN_PHYSICAL_STATE")
        with self.assertRaises(PhysicalResourceClaimError):
            self.authority.claim(self.resource.physical_resource_id, "owner-b")
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            self.authority.snapshot(self.resource.physical_resource_id).state,
        )

    def test_t12_reconciliation_requires_evidence(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(claim)
        self.authority.quarantine(claim, "BACKEND_CRASH")
        with self.assertRaises(PhysicalResourceStateError):
            self.authority.reconcile(
                self.resource.physical_resource_id,
                evidence="",
            )
        snapshot = self.authority.snapshot(self.resource.physical_resource_id)
        with self.assertRaises(PhysicalResourceStateError):
            self.authority.reconcile(
                self.resource.physical_resource_id,
                evidence=_issue_physical_release_evidence(
                    provider=self.resource.provider,
                    evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
                    physical_resource_id=snapshot.physical_resource_id,
                    claim_id=snapshot.claim_id,
                    execution_generation=snapshot.execution_generation,
                    operation_id=snapshot.operation_id,
                    observation="wrong evidence type",
                ),
            )
        reconciled = self.authority.reconcile(
            self.resource.physical_resource_id,
            evidence=self._sanitization_evidence(
                snapshot,
                observation="backend recreated and surface verified free",
            ),
        )
        self.assertEqual(PhysicalResourceState.AVAILABLE, reconciled.state)
        self.assertIsNone(reconciled.owner)

    def test_t12b_public_evidence_constructor_is_blocked(self) -> None:
        with self.assertRaises(TypeError):
            from bot_ia.core.physical_resource_authority import PhysicalReleaseEvidence

            PhysicalReleaseEvidence(
                provider=self.resource.provider,
                evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
                evidence_level="VERIFIED",
                physical_resource_id=self.resource.physical_resource_id,
            )

    def test_t12c_active_release_rejects_arbitrary_and_empty_strings(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(claim, operation_id="op-active")
        for evidence in ("arbitrary", ""):
            with self.assertRaises(PhysicalResourceStateError):
                self.authority.release(claim, evidence=evidence)
        self.assertEqual(
            PhysicalResourceState.BUSY,
            self.authority.snapshot(self.resource.physical_resource_id).state,
        )

    def test_t12d_active_release_accepts_matching_typed_evidence(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(claim, operation_id="op-active")
        released = self.authority.release(
            claim,
            evidence=self._termination_evidence(
                claim,
                operation_id="op-active",
            ),
        )
        self.assertEqual(PhysicalResourceState.AVAILABLE, released.state)

    def test_t12e_sanitization_requires_matching_quarantine_context(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(
            claim,
            backend="qweb",
            operation_id="op-sanitize",
        )
        self.authority.quarantine(claim, "TERMINATION_UNCONFIRMED")
        snapshot = self.authority.snapshot(self.resource.physical_resource_id)
        wrong = _issue_physical_release_evidence(
            provider=self.resource.provider,
            evidence_type=PhysicalReleaseEvidenceType.SANITIZATION,
            physical_resource_id=snapshot.physical_resource_id,
            claim_id="wrong-claim",
            execution_generation=snapshot.execution_generation,
            operation_id=snapshot.operation_id,
            observation="wrong claim",
        )
        with self.assertRaises(PhysicalResourceStateError):
            self.authority.reconcile(
                self.resource.physical_resource_id,
                evidence=wrong,
            )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            self.authority.snapshot(self.resource.physical_resource_id).state,
        )
        released = self.authority.reconcile(
            self.resource.physical_resource_id,
            evidence=self._sanitization_evidence(snapshot),
        )
        self.assertEqual(PhysicalResourceState.AVAILABLE, released.state)

    def test_t12f_active_release_rejects_stale_generation_claim_resource_and_operation(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(claim, operation_id="op-current")
        snapshot = self.authority.snapshot(self.resource.physical_resource_id)
        variants = (
            _issue_physical_release_evidence(
                provider=snapshot.provider,
                evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
                physical_resource_id=snapshot.physical_resource_id,
                claim_id=snapshot.claim_id,
                execution_generation=snapshot.execution_generation + 1,
                operation_id=snapshot.operation_id,
            ),
            _issue_physical_release_evidence(
                provider=snapshot.provider,
                evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
                physical_resource_id=snapshot.physical_resource_id,
                claim_id="wrong-claim",
                execution_generation=snapshot.execution_generation,
                operation_id=snapshot.operation_id,
            ),
            _issue_physical_release_evidence(
                provider=snapshot.provider,
                evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
                physical_resource_id="wrong-resource",
                claim_id=snapshot.claim_id,
                execution_generation=snapshot.execution_generation,
                operation_id=snapshot.operation_id,
            ),
            _issue_physical_release_evidence(
                provider=snapshot.provider,
                evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
                physical_resource_id=snapshot.physical_resource_id,
                claim_id=snapshot.claim_id,
                execution_generation=snapshot.execution_generation,
                operation_id="wrong-operation",
            ),
        )
        for evidence in variants:
            with self.assertRaises(PhysicalResourceStateError):
                self.authority.release(claim, evidence=evidence)
        self.assertEqual(
            PhysicalResourceState.BUSY,
            self.authority.snapshot(self.resource.physical_resource_id).state,
        )

    def test_t13_concurrent_claims_have_one_winner(self) -> None:
        barrier = threading.Barrier(8)
        results = []
        results_lock = threading.Lock()

        def attempt(index: int) -> None:
            barrier.wait()
            try:
                claim = self.authority.claim(
                    self.resource.physical_resource_id,
                    f"owner-{index}",
                )
                result = ("success", claim.owner)
            except PhysicalResourceClaimError:
                result = ("denied", None)
            with results_lock:
                results.append(result)

        threads = [
            threading.Thread(target=attempt, args=(index,))
            for index in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(1, sum(result[0] == "success" for result in results))
        self.assertEqual(7, sum(result[0] == "denied" for result in results))

    def test_t14_snapshot_is_immutable(self) -> None:
        snapshot = self.authority.snapshot(self.resource.physical_resource_id)
        with self.assertRaises(AttributeError):
            snapshot.state = PhysicalResourceState.BUSY

    def test_t15_release_is_idempotent_before_a_new_claim(self) -> None:
        first = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        first_release = self.authority.release(first)
        second_release = self.authority.release(first)
        self.assertEqual(first_release, second_release)
        current = self.authority.snapshot(self.resource.physical_resource_id)
        self.assertEqual(PhysicalResourceState.AVAILABLE, current.state)
        second = self.authority.claim(self.resource.physical_resource_id, "owner-b")
        with self.assertRaises(PhysicalResourceOwnershipError):
            self.authority.release(first)
        self.assertEqual(second.claim_id, self.authority.snapshot(
            self.resource.physical_resource_id
        ).claim_id)

    def test_t16_stale_fencing_same_generation_operation_is_rejected(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(claim, operation_id="op-current")
        self.assertFalse(
            self.authority.validate_execution(
                self.resource.physical_resource_id,
                claim.claim_id,
                claim.execution_generation,
                operation_id="op-stale",
            )
        )

    def test_claimed_state_is_not_executing_until_begin(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.assertEqual(
            PhysicalResourceState.CLAIMING,
            self.authority.snapshot(self.resource.physical_resource_id).state,
        )
        self.assertFalse(
            self.authority.validate_execution(
                self.resource.physical_resource_id,
                claim.claim_id,
                claim.execution_generation,
            )
        )

    def test_cancel_transition_requires_owner(self) -> None:
        claim = self.authority.claim(self.resource.physical_resource_id, "owner-a")
        self.authority.begin_execution(claim)
        cancelled = self.authority.request_cancel(claim)
        self.assertEqual(PhysicalResourceState.CANCELLING, cancelled.state)

    def test_invalid_reconcile_from_available_is_rejected(self) -> None:
        with self.assertRaises(PhysicalResourceStateError):
            self.authority.reconcile(
                self.resource.physical_resource_id,
                evidence="not quarantined",
            )


if __name__ == "__main__":
    unittest.main()
