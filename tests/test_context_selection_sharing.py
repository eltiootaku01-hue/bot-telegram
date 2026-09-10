from __future__ import annotations

import unittest
from pathlib import Path

from bot_ia.contracts import AuthorityLevel, CanonStatus, Confidence, EpistemicStatus, EvidenceStatus, SourceRecord, SourceStatus
from bot_ia.core.context_selection import select_context_sources
from bot_ia.core.context_sharing import build_shared_context
from bot_ia.core.local_workflow import LocalExecution
from bot_ia.librarian.models import CatalogEntry, Coverage, CoverageStatus, EvidencePack, Fragment, RankedSource, RetrievalQuery, SourceMetadata, SourceType


class ContextSelectionSharingTests(unittest.TestCase):
    def _execution(self) -> LocalExecution:
        sources = ("canon_a", "canon_b")
        evidence = EvidencePack(
            query=RetrievalQuery("Kuro Hitomi", "one_neko_punch"),
            sources=tuple(self._ranked_source(source_id) for source_id in sources),
            fragments=(
                Fragment("canon_a", "one_neko_punch", 0, 1, 2, "Kuro existe.", 1.0),
                Fragment("canon_b", "one_neko_punch", 0, 3, 4, "Hitomi observa a Kuro.", 0.9),
            ),
            ranking_explanation=(), conflicts=(), omissions=(), confidence=Confidence.HIGH,
            source_versions=(("canon_a", "v1"), ("canon_b", "v2")),
            coverage=Coverage(CoverageStatus.ESTABLISHED, 2, 2, 0),
        )
        return LocalExecution("resultado", True, evidence, None, None, None, None)

    @staticmethod
    def _ranked_source(source_id: str) -> RankedSource:
        record = SourceRecord(source_id, "one_neko_punch", "chapter", AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, Path(f"{source_id}.md"), "hash", CanonStatus.CANON)
        metadata = SourceMetadata(source_id, SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON)
        entry = CatalogEntry(record, metadata, "contenido", "hash")
        return RankedSource(entry, 1.0, 1.0, EvidenceStatus.FOUND, EpistemicStatus.ESTABLISHED, Confidence.HIGH, ())

    def test_shared_packet_contains_only_explicitly_selected_source(self) -> None:
        selected = select_context_sources(self._execution(), ("canon_b",))
        shared = build_shared_context(selected)
        self.assertEqual(shared.source_ids, ("canon_b",))
        self.assertIn("Hitomi observa a Kuro.", shared.text)
        self.assertNotIn("Kuro existe.", shared.text)
        self.assertEqual(shared.source_versions, (("canon_b", "v2"),))

    def test_sharing_never_recovers_an_unselected_source(self) -> None:
        execution = self._execution()
        selected = select_context_sources(execution, ("canon_a",))
        shared = build_shared_context(selected)
        self.assertEqual(shared.source_ids, ("canon_a",))
        self.assertNotIn("canon_b", shared.text)
        self.assertNotIn("Hitomi observa a Kuro.", shared.text)


if __name__ == "__main__":
    unittest.main()
