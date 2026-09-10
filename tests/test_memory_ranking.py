from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bot_ia.contracts import Confidence, UniverseDefinition, UniverseRegistry
from bot_ia.memory import MemoryStore, MemoryType


class MemoryRankingTests(unittest.TestCase):
    def test_retrieval_prefers_higher_confidence_when_relevance_ties(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = UniverseRegistry()
            registry.register(UniverseDefinition("test_world", "Test World", root / "biblioteca"))
            store = MemoryStore(root, registry)
            low = store.propose(
                universe_id="test_world",
                user_id="user",
                conversation_id="conversation",
                memory_type=MemoryType.NOTE,
                content="Kuro prefiere pescado fresco.",
                source="test-low",
                provenance="fixture-low",
                confidence=Confidence.LOW,
            )
            high = store.propose(
                universe_id="test_world",
                user_id="user",
                conversation_id="conversation",
                memory_type=MemoryType.NOTE,
                content="Kuro prefiere pescado fresco.",
                source="test-high",
                provenance="fixture-high",
                confidence=Confidence.HIGH,
            )
            store.approve(low.memory_id, approved_by_author="test")
            store.approve(high.memory_id, approved_by_author="test")

            matches = store.retrieve(
                universe_id="test_world",
                user_id="user",
                conversation_id="conversation",
                query="Kuro pescado",
                limit=2,
            )

            self.assertEqual([match.record.memory_id for match in matches], [high.memory_id, low.memory_id])


if __name__ == "__main__":
    unittest.main()
