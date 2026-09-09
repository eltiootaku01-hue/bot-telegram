from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from bot_ia.context import ContextBuilder, TokenBudget
from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceStatus, UniverseDefinition, UniverseRegistry
from bot_ia.librarian import LocalLibrarian, RetrievalQuery, SourceInventory, SourceMetadata, SourceType, SpoilerLevel, SpoilerScope, TemporalScope
from bot_ia.memory import MemoryStatus, MemoryStorageError, MemoryStore, MemoryType

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


class Phase8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.registry = UniverseRegistry()
        self.registry.register(UniverseDefinition("one_neko_punch", "One Neko Punch", self.root / "one"))
        self.registry.register(UniverseDefinition("other_world", "Other World", self.root / "other"))
        self.store = MemoryStore(self.root, self.registry)

    def tearDown(self) -> None:
        self.store.close(); self.temp.cleanup()

    def proposed(self, **changes):
        values = dict(universe_id="one_neko_punch", user_id="u1", conversation_id="c1", memory_type=MemoryType.NARRATIVE_CONTEXT, content="Kuro usa humor sarcástico", source="conversation", provenance="conversation:c1", tags=("kuro", "sarcastico"))
        values.update(changes); return self.store.propose(**values)

    def active(self, **changes):
        return self.store.approve(self.proposed(**changes).memory_id, approved_by_author="author")

    def test_creates_proposed_memory(self): self.assertEqual(MemoryStatus.PROPOSED, self.proposed().status)
    def test_unapproved_memory_is_not_retrieved(self): self.proposed(); self.assertEqual((), self.store.retrieve(universe_id="one_neko_punch", user_id="u1", conversation_id="c1", query="Kuro"))
    def test_authorization_makes_memory_active(self): self.assertTrue(self.active().approved_by_author); self.assertEqual(MemoryStatus.ACTIVE, self.active(content="otra nota").status)
    def test_revocation_prevents_retrieval(self):
        record=self.active(); self.store.revoke(record.memory_id); self.assertEqual((), self.store.retrieve(universe_id="one_neko_punch", user_id="u1", conversation_id="c1", query="Kuro"))
    def test_expiration_prevents_retrieval(self):
        expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        record = self.active(expires_at=expires_at)
        self.assertTrue(self.store.retrieve(universe_id="one_neko_punch", user_id="u1", conversation_id="c1", query="Kuro"))
        self.store.expire_due(expires_at)
        self.assertEqual(MemoryStatus.EXPIRED, self.store.get(record.memory_id).status)
        self.assertEqual((), self.store.retrieve(universe_id="one_neko_punch", user_id="u1", conversation_id="c1", query="Kuro", now=expires_at))
    def test_invalid_expiration_is_rejected(self):
        with self.assertRaises(ValueError): self.proposed(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    def test_user_isolation(self):
        self.active(); self.assertEqual((), self.store.retrieve(universe_id="one_neko_punch", user_id="u2", conversation_id="c1", query="Kuro"))
    def test_universe_isolation_no_contamination(self):
        self.active(); self.assertEqual((), self.store.retrieve(universe_id="other_world", user_id="u1", conversation_id="c1", query="Kuro"))
    def test_conflict_never_changes_canon(self):
        record=self.active(); conflict=self.store.record_conflict(record.memory_id, "chapter_001"); self.assertEqual(MemoryStatus.CONFLICT, conflict.status); self.assertEqual(("chapter_001",), conflict.conflicts_with)
    def test_relevant_memory_enters_context_but_irrelevant_does_not(self):
        relevant=self.active(); irrelevant=self.active(content="Mika prefiere té", tags=("mika",))
        source=self.root / "chapter.md"; source.write_text("Kuro protege.", encoding="utf-8")
        metadata={"chapter.md": SourceMetadata("chapter", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON, TemporalScope(), SpoilerScope(SpoilerLevel.NONE))}
        pack=LocalLibrarian().retrieve(RetrievalQuery("Kuro", "one_neko_punch"), SourceInventory(self.root).discover("one_neko_punch", metadata))
        matches=self.store.retrieve(universe_id="one_neko_punch", user_id="u1", conversation_id="c1", query="Kuro")
        context=ContextBuilder().build(pack, TokenBudget(100), memory_matches=matches)
        self.assertIn(relevant.content, context.text); self.assertNotIn(irrelevant.content, context.text); self.assertIn("MEMORY (non-canon)", context.text)
    def test_supersedes_archives_old_memory(self):
        old=self.active(); replacement=self.active(content="Kuro usa humor seco"); updated=self.store.supersede(old.memory_id, replacement.memory_id); self.assertEqual(old.memory_id, updated.supersedes); self.assertEqual(MemoryStatus.ARCHIVED, self.store.get(old.memory_id).status)
    def test_persists_after_close_and_reopen(self):
        record=self.active(); self.store.close(); reopened=MemoryStore(self.root, self.registry); self.assertEqual(record.memory_id, reopened.retrieve(universe_id="one_neko_punch", user_id="u1", conversation_id="c1", query="Kuro")[0].record.memory_id); reopened.close()
    def test_invalid_disk_record_is_controlled_error(self):
        db = sqlite3.connect(self.store.path)
        try:
            db.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("bad", "one_neko_punch", "u1", None, "bad", "x", "source", NOW.isoformat(), NOW.isoformat(), 1, "active", "high", None, None, "[]", "[]", "p", None, "[]"))
            db.commit()
        finally:
            db.close()
        with self.assertRaises(MemoryStorageError): self.store.get("bad")
    def test_transaction_rolls_back_after_error(self):
        record = self.active()
        with self.assertRaises(RuntimeError):
            with self.store._transaction() as db:
                db.execute("UPDATE memories SET status=? WHERE memory_id=?", ("archived", record.memory_id))
                raise RuntimeError("test rollback")
        self.assertEqual(MemoryStatus.ACTIVE, self.store.get(record.memory_id).status)
    def test_secrets_and_unknown_universe_are_rejected(self):
        with self.assertRaises(MemoryStorageError): self.proposed(content="sk-abcdefghijklmnopqrstuvwxyz")
        with self.assertRaises(MemoryStorageError): self.proposed(universe_id="unknown_world")
    def test_archiving_retains_auditable_record(self):
        record=self.active(); self.store.archive(record.memory_id); self.assertEqual(MemoryStatus.ARCHIVED, self.store.get(record.memory_id).status)


if __name__ == "__main__": unittest.main()
