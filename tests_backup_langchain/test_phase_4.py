from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from bot_ia.context import CacheEntry, CacheStatus, ContextBuilder, ContextCache, TokenBudget, build_cache_key
from bot_ia.context.trace import build_trace
from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceStatus
from bot_ia.librarian import LocalLibrarian, RetrievalQuery, SourceInventory, SourceMetadata, SourceType, SpoilerLevel, SpoilerScope, TemporalScope


class Phase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "chapter.md").write_text("Kuro protege la ciudad.\n\nKuro habla con Hitomi.", encoding="utf-8")
        (root / "plan.md").write_text("Kuro viajara al norte.", encoding="utf-8")
        metadata = {
            "chapter.md": SourceMetadata("chapter", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON, TemporalScope("manga", "inicio", 1, 1), SpoilerScope(SpoilerLevel.NONE)),
            "plan.md": SourceMetadata("plan", SourceType.PLANNING, AuthorityLevel.PLAN, SourceStatus.VALIDATED, CanonStatus.PLANNING, TemporalScope("manga", "future", 8, 8), SpoilerScope(SpoilerLevel.LOW)),
        }
        self.entries = SourceInventory(root).discover("one_neko_punch", metadata)
        self.librarian = LocalLibrarian()
        self.builder = ContextBuilder()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def pack(self, text: str, universe: str = "one_neko_punch"):
        return self.librarian.retrieve(RetrievalQuery(text, universe), self.entries)

    def test_minimum_context_is_sufficient(self) -> None:
        context = self.builder.build(self.pack("protege"), TokenBudget(100))
        self.assertTrue(context.sufficient)
        self.assertIn("Kuro protege", context.text)

    def test_shown_evidence_is_prioritized(self) -> None:
        context = self.builder.build(self.pack("Kuro"), TokenBudget(100))
        evidence = [item for item in context.selections if item.kind == "evidence"]
        self.assertEqual("chapter", evidence[0].source_id)

    def test_planning_is_excluded_for_non_future_task(self) -> None:
        context = self.builder.build(self.pack("viajara"), TokenBudget(100))
        self.assertFalse(context.sufficient)
        self.assertIn("omitted_planning:plan", context.omissions)

    def test_planning_is_included_for_future_task(self) -> None:
        context = self.builder.build(self.pack("viajara"), TokenBudget(100), future_task=True)
        self.assertTrue(context.sufficient)
        self.assertIn("viajara", context.text)

    def test_context_respects_token_limit(self) -> None:
        context = self.builder.build(self.pack("Kuro"), TokenBudget(8))
        self.assertLessEqual(context.estimated_tokens, 8)

    def test_budget_omissions_are_recorded(self) -> None:
        context = self.builder.build(self.pack("Kuro"), TokenBudget(8))
        self.assertTrue(context.excessive)
        self.assertTrue(any("budget" in item for item in context.omissions))

    def test_context_is_insufficient_without_evidence(self) -> None:
        context = self.builder.build(self.pack("inexistente"), TokenBudget(100))
        self.assertFalse(context.sufficient)
        self.assertIn("NO_ENCONTRADO", context.omissions)

    def test_cache_miss_then_hit(self) -> None:
        pack, context, cache = self.pack("protege"), self.builder.build(self.pack("protege"), TokenBudget(100)), ContextCache()
        key = build_cache_key(pack, "factual", context.algorithm_version)
        self.assertEqual(CacheStatus.MISS, cache.get(key).status)
        cache.put(CacheEntry(key, "one_neko_punch", context, context.source_versions, datetime.now(timezone.utc)))
        self.assertEqual(CacheStatus.HIT, cache.get(key).status)

    def test_cache_invalidates_when_hash_changes(self) -> None:
        pack, context, cache = self.pack("protege"), self.builder.build(self.pack("protege"), TokenBudget(100)), ContextCache()
        key = build_cache_key(pack, "factual", context.algorithm_version)
        cache.put(CacheEntry(key, "one_neko_punch", context, context.source_versions, datetime.now(timezone.utc)))
        self.assertEqual(1, cache.invalidate_source("chapter", "different-hash"))
        self.assertEqual(CacheStatus.MISS, cache.get(key).status)

    def test_cache_isolated_by_universe(self) -> None:
        pack, context = self.pack("protege"), self.builder.build(self.pack("protege"), TokenBudget(100))
        other = self.librarian.retrieve(RetrievalQuery("protege", "other_world"), self.entries)
        self.assertNotEqual(build_cache_key(pack, "factual", context.algorithm_version), build_cache_key(other, "factual", context.algorithm_version))

    def test_context_isolated_by_universe(self) -> None:
        other = self.librarian.retrieve(RetrievalQuery("protege", "other_world"), self.entries)
        context = self.builder.build(other, TokenBudget(100))
        self.assertEqual("other_world", context.universe_id)
        self.assertFalse(context.sufficient)

    def test_trace_contains_only_retrieval_metadata(self) -> None:
        pack, context = self.pack("protege"), self.builder.build(self.pack("protege"), TokenBudget(100))
        trace = build_trace("request-1", "factual", "search", pack, context, "miss")
        self.assertEqual(("chapter",), trace.source_ids)
        self.assertEqual("one_neko_punch", trace.universe_id)
        self.assertTrue(trace.source_versions)

    def test_cache_expiration_is_optional_and_enforced(self) -> None:
        pack, context, cache = self.pack("protege"), self.builder.build(self.pack("protege"), TokenBudget(100)), ContextCache()
        key = build_cache_key(pack, "factual", context.algorithm_version)
        now = datetime.now(timezone.utc)
        cache.put(CacheEntry(key, "one_neko_punch", context, context.source_versions, now, now + timedelta(seconds=1)))
        self.assertEqual(CacheStatus.EXPIRED, cache.get(key, now + timedelta(seconds=1)).status)


if __name__ == "__main__":
    unittest.main()
