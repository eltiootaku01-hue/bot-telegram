# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bot_ia.supervisor import (
    ChangeBudget,
    Claim,
    ClaimStatus,
    ClaimStore,
    Confidence,
    Evidence,
    EvidenceStatus,
    EvidenceStore,
    EvidenceType,
    ScopeLock,
    ScopeOperation,
)


class ClaimsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = EvidenceStore(Path(self.temp.name) / "evidence")
        self.claims = ClaimStore(self.store)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _evidence(self) -> Evidence:
        evidence = Evidence.create(
            evidence_type=EvidenceType.FILE_EVIDENCE,
            source="test",
            scope="unit",
            result=EvidenceStatus.OBSERVED,
        )
        self.store.add(evidence)
        return evidence

    def _claim(self, **kwargs: object) -> Claim:
        claim = Claim.create(
            statement="sample exists",
            source="test",
            scope="unit",
            **kwargs,
        )
        return self.claims.add(claim)

    def test_create_claim_defaults_to_unknown(self) -> None:
        claim = self._claim()
        self.assertEqual(ClaimStatus.UNKNOWN, claim.status)
        self.assertEqual(Confidence.UNKNOWN, claim.confidence)

    def test_link_existing_evidence(self) -> None:
        evidence = self._evidence()
        claim = self._claim()
        self.claims.link_evidence(claim.claim_id, evidence.evidence_id)
        validation = self.claims.validate(claim.claim_id)
        self.assertTrue(validation.evidence_exists)

    def test_missing_evidence_cannot_be_verified(self) -> None:
        claim = self._claim(evidence_ids=["missing"])
        self.assertEqual(["missing"], list(self.claims.validate(claim.claim_id).missing_evidence_ids))
        with self.assertRaises(ValueError):
            self.claims.set_confidence(claim.claim_id, Confidence.VERIFIED)

    def test_claim_statuses_remain_explicit(self) -> None:
        for status in ClaimStatus:
            claim = self._claim()
            self.claims.set_status(claim.claim_id, status)
            self.assertEqual(status, claim.status)

    def test_verified_confidence_requires_evidence(self) -> None:
        evidence = self._evidence()
        claim = self._claim(evidence_ids=[evidence.evidence_id])
        self.claims.set_confidence(claim.claim_id, Confidence.VERIFIED)
        self.assertEqual(Confidence.VERIFIED, claim.confidence)

    def test_lost_evidence_is_observable(self) -> None:
        evidence = self._evidence()
        claim = self._claim(evidence_ids=[evidence.evidence_id])
        self.claims.set_confidence(claim.claim_id, Confidence.VERIFIED)
        self.store._evidence_path.unlink()
        validation = self.claims.validate(claim.claim_id)
        self.assertFalse(validation.evidence_exists)
        self.assertEqual(Confidence.UNKNOWN, self.claims.effective_confidence(claim.claim_id))


class ScopeLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs" / "project_memory").mkdir(parents=True)
        (self.root / "src").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _scope(self, **kwargs: object) -> ScopeLock:
        return ScopeLock.create(
            scope_id="scope-1",
            task_id="task-1",
            repository_root=self.root,
            allowed_paths=("docs/project_memory/**",),
            forbidden_paths=(),
            allowed_operations=(ScopeOperation.READ, ScopeOperation.WRITE),
            scope_owner="supervisor",
            authorization="contract-only",
            change_budget=ChangeBudget(3, 100, 100, 2, 3),
            **kwargs,
        )

    def test_allowed_path_and_operation(self) -> None:
        self.assertTrue(self._scope().authorize(ScopeOperation.READ, "docs/project_memory/a.md"))

    def test_default_deny_for_unlisted_path(self) -> None:
        self.assertFalse(self._scope().authorize(ScopeOperation.READ, "src/a.py"))

    def test_forbidden_operation_overrides_allowed(self) -> None:
        scope = self._scope(forbidden_operations=(ScopeOperation.WRITE,))
        self.assertFalse(scope.authorize(ScopeOperation.WRITE, "docs/project_memory/a.md"))

    def test_traversal_is_denied(self) -> None:
        self.assertFalse(self._scope().authorize(ScopeOperation.READ, "docs/project_memory/../../src/a.py"))

    def test_absolute_outside_scope_is_denied(self) -> None:
        outside = self.root.parent / "outside.txt"
        self.assertFalse(self._scope().authorize(ScopeOperation.READ, outside))

    def test_symlink_escape_is_denied(self) -> None:
        target = self.root.parent / "outside-dir"
        target.mkdir()
        (self.root / "docs" / "project_memory" / "escape").symlink_to(target, target_is_directory=True)
        self.assertFalse(self._scope().authorize(ScopeOperation.READ, "docs/project_memory/escape/secret.txt"))

    def test_change_budget(self) -> None:
        scope = self._scope()
        self.assertTrue(scope.check_change_budget(files_changed=3, lines_added=100, lines_deleted=100, commits=2, repair_attempts=3))
        self.assertFalse(scope.check_change_budget(files_changed=4, lines_added=100, lines_deleted=100, commits=2, repair_attempts=3))
        self.assertFalse(scope.check_change_budget(files_changed=3, lines_added=101, lines_deleted=100, commits=2, repair_attempts=3))

    def test_invalid_scope_requires_contract_fields(self) -> None:
        with self.assertRaises(ValueError):
            ScopeLock.create(
                scope_id="",
                task_id="task-1",
                repository_root=self.root,
                scope_owner="supervisor",
                authorization="contract-only",
            )
