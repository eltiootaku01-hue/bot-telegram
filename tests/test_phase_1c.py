from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from bot_ia.change_management import ChangeManager, PathOutsideWorkspaceError
from bot_ia.contracts import AuthorityLevel, CanonStatus, Confidence, DuplicateUniverseError, MemoryRecord, SessionState, SourceRecord, SourceStatus, UniverseDefinition, UniverseNotFoundError, UniverseRegistry
from bot_ia.policy import evaluate_authority

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


def source(**changes: object) -> SourceRecord:
    values: dict[str, object] = {"source_id": "chapter_001", "universe_id": "one_neko_punch", "source_type": "chapter", "authority": AuthorityLevel.PRIMARY, "status": SourceStatus.VALIDATED, "path": Path("sources/chapter_001.txt"), "content_hash": "a" * 64, "canon_status": CanonStatus.CANON}
    values.update(changes)
    return SourceRecord(**values)  # type: ignore[arg-type]


class ContractTests(unittest.TestCase):
    def test_primary_source_separates_canon_evidence_and_epistemology(self) -> None:
        decision = evaluate_authority(source())
        self.assertEqual(CanonStatus.CANON, decision.canon)
        self.assertEqual("found", decision.evidence.value)
        self.assertEqual("established", decision.epistemic.value)
        self.assertEqual(Confidence.HIGH, decision.confidence)

    def test_plan_is_evidence_but_not_established_canon(self) -> None:
        decision = evaluate_authority(source(authority=AuthorityLevel.PLAN))
        self.assertEqual(CanonStatus.PLANNING, decision.canon)
        self.assertEqual("found", decision.evidence.value)
        self.assertEqual("not_established", decision.epistemic.value)

    def test_conflicted_source_never_resolves_as_fact(self) -> None:
        decision = evaluate_authority(source(status=SourceStatus.CONFLICTED))
        self.assertEqual(CanonStatus.CONFLICTED, decision.canon)
        self.assertEqual("conflict", decision.evidence.value)
        self.assertEqual("conflict", decision.epistemic.value)

    def test_unvalidated_source_is_unverified(self) -> None:
        decision = evaluate_authority(source(status=SourceStatus.PENDING))
        self.assertEqual("unverified", decision.evidence.value)
        self.assertEqual("not_established", decision.epistemic.value)

    def test_universe_id_is_required_and_validated(self) -> None:
        with self.assertRaises(ValueError):
            source(universe_id="One Neko Punch")

    def test_registry_isolates_universes_with_same_conceptual_name(self) -> None:
        registry = UniverseRegistry()
        first = UniverseDefinition("one_neko_punch", "One Neko Punch", Path("data/one"))
        second = UniverseDefinition("alternate_neko", "One Neko Punch", Path("data/two"))
        registry.register(first)
        registry.register(second)
        self.assertEqual(Path("data/one"), registry.get("one_neko_punch").root_path)
        self.assertEqual(Path("data/two"), registry.get("alternate_neko").root_path)

    def test_registry_rejects_duplicate_and_unknown_universes(self) -> None:
        registry = UniverseRegistry()
        definition = UniverseDefinition("one_neko_punch", "One Neko Punch", Path("data/one"))
        registry.register(definition)
        with self.assertRaises(DuplicateUniverseError):
            registry.register(definition)
        with self.assertRaises(UniverseNotFoundError):
            registry.get("unknown_world")

    def test_session_state_expires_at_exact_time(self) -> None:
        state = SessionState("session-1", "one_neko_punch", NOW + timedelta(minutes=1))
        self.assertFalse(state.is_expired(NOW))
        self.assertTrue(state.is_expired(NOW + timedelta(minutes=1)))

    def test_memory_requires_authorization_and_respects_expiry(self) -> None:
        denied = MemoryRecord("m1", "one_neko_punch", "secret", False, "session", "test")
        allowed = MemoryRecord("m2", "one_neko_punch", "approved", True, "session", "test", created_at=NOW, expires_at=NOW + timedelta(days=1))
        self.assertFalse(denied.usable_at(NOW))
        self.assertTrue(allowed.usable_at(NOW))
        self.assertFalse(allowed.usable_at(NOW + timedelta(days=1)))


class ChangeManagerTests(unittest.TestCase):
    def test_checkpoint_detects_file_change_and_validates_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "note.txt"
            target.write_text("before", encoding="utf-8")
            manager = ChangeManager(root)
            checkpoint = manager.precheck("note.txt")
            target.write_text("after", encoding="utf-8")
            self.assertTrue(manager.detect_change(checkpoint).changed)
            self.assertTrue(manager.validate(checkpoint, must_exist=True).valid)

    def test_checkpoint_detects_creation_and_missing_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = ChangeManager(root)
            checkpoint = manager.precheck("created.txt")
            (root / "created.txt").write_text("created", encoding="utf-8")
            self.assertTrue(manager.detect_change(checkpoint).changed)
            self.assertTrue(manager.validate(checkpoint, must_exist=True).valid)
            self.assertFalse(manager.validate(checkpoint, must_exist=False).valid)

    def test_manager_rejects_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manager = ChangeManager(Path(temp))
            with self.assertRaises(PathOutsideWorkspaceError):
                manager.precheck("../outside.txt")

    def test_manager_rejects_directory_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "folder").mkdir()
            with self.assertRaises(ValueError):
                ChangeManager(root).precheck("folder")


if __name__ == "__main__":
    unittest.main()
