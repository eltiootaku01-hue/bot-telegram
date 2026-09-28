# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from bot_ia.supervisor import (
    Confidence,
    Evidence,
    EvidenceStatus,
    EvidenceStore,
    EvidenceType,
    ObservationCore,
)


class ObservationCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.repo,
            check=True,
        )
        (self.repo / "sample.txt").write_bytes(b"hello\n")
        subprocess.run(["git", "add", "sample.txt"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "initial"],
            cwd=self.repo,
            check=True,
        )
        self.store_path = self.root / "evidence"
        self.core = ObservationCore(self.repo, self.store_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_evidence_storage_inside_repository_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ObservationCore(self.repo, self.repo / ".supervisor")

    def test_repository_head_branch_and_clean_state(self) -> None:
        result = self.core.observe_repository()
        head = result["head_observation"]
        working = result["working_tree_observation"]
        self.assertEqual("REPOSITORY_HEAD", head.observation_type)
        self.assertEqual(40, len(head.value))
        self.assertEqual([], working.value)

    def test_repository_detects_changes(self) -> None:
        (self.repo / "sample.txt").write_bytes(b"changed\n")
        result = self.core.observe_repository()
        changed = result["changed_files_observation"]
        self.assertEqual(["sample.txt"], changed.value)

    def test_file_exists_and_hash(self) -> None:
        observed = self.core.observe_file("sample.txt")
        hashed = self.core.hash_file("sample.txt")
        self.assertTrue(observed.value)
        self.assertEqual(
            hashlib.sha256(b"hello\n").hexdigest(),
            hashed.value,
        )

    def test_missing_file_is_unknown(self) -> None:
        observed = self.core.hash_file("missing.txt")
        self.assertEqual(EvidenceStatus.UNKNOWN, observed.status)

    def test_evidence_round_trip_and_persistence(self) -> None:
        evidence = Evidence.create(
            evidence_type=EvidenceType.TEST_EVIDENCE,
            source="test",
            scope="unit",
            result=EvidenceStatus.TESTED,
            exit_code=0,
        )
        self.core.store.add(evidence)
        reloaded = EvidenceStore(self.store_path).get(evidence.evidence_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(EvidenceStatus.TESTED, reloaded.result)
        self.assertEqual(Confidence.INSPECTED, reloaded.confidence)

    def test_confidence_is_controlled(self) -> None:
        evidence = Evidence.create(
            evidence_type=EvidenceType.TEST_EVIDENCE,
            source="test",
            scope="unit",
            result=EvidenceStatus.TESTED,
        )
        self.core.store.add(evidence)
        verified = self.core.update_confidence(
            evidence.evidence_id,
            Confidence.VERIFIED,
        )
        self.assertEqual(Confidence.VERIFIED, verified.confidence)
        with self.assertRaises(ValueError):
            self.core.update_confidence(
                evidence.evidence_id,
                Confidence.INFERRED,
            )

    def test_unauthorized_command_is_blocked(self) -> None:
        evidence = self.core.run_command(["git", "push"], scope="safety")
        self.assertEqual(EvidenceStatus.BLOCKED, evidence.result)
        self.assertIsNone(evidence.exit_code)
        self.assertEqual(
            "COMMAND_NOT_AUTHORIZED",
            evidence.metadata["reason"],
        )

    def test_authorized_read_only_command(self) -> None:
        evidence = self.core.run_command(["git", "rev-parse", "HEAD"])
        self.assertEqual(EvidenceStatus.TESTED, evidence.result)
        self.assertEqual(0, evidence.exit_code)
        self.assertEqual(40, len(evidence.metadata["stdout"].strip()))
        self.assertTrue(self.core.verify_command_result(evidence))

    def test_exit_code_mismatch_is_not_verified(self) -> None:
        evidence = self.core.run_command(["git", "rev-parse", "HEAD"])
        self.assertFalse(
            self.core.verify_command_result(evidence, expected_exit_code=1)
        )

    def test_basic_diff_is_read_only_evidence(self) -> None:
        (self.repo / "sample.txt").write_bytes(b"changed\n")
        evidence = self.core.diff()
        self.assertEqual(EvidenceStatus.TESTED, evidence.result)
        self.assertEqual(0, evidence.exit_code)
        self.assertIn("sample.txt", evidence.metadata["stdout"])

    def test_audit_links_evidence(self) -> None:
        evidence = self.core.run_command(["git", "rev-parse", "HEAD"])
        audit = self.core.store.list_audit()
        matching = [
            event for event in audit
            if event.evidence_id == evidence.evidence_id
        ]
        self.assertTrue(matching)

    def test_observation_does_not_modify_repository_file(self) -> None:
        before = (self.repo / "sample.txt").read_bytes()
        self.core.observe_file("sample.txt")
        self.core.hash_file("sample.txt")
        self.core.observe_repository()
        after = (self.repo / "sample.txt").read_bytes()
        self.assertEqual(before, after)

    def test_observation_does_not_modify_git_state(self) -> None:
        before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.core.observe_repository()
        after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
