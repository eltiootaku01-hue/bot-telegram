from __future__ import annotations

import unittest
from dataclasses import replace

from bot_ia.core.context_selection import available_context_sources, select_context_sources
from bot_ia.core.local_workflow import LocalExecution
from bot_ia.librarian.models import EvidencePack, Fragment


class ContextSelectionTests(unittest.TestCase):
    def _execution(self) -> LocalExecution:
        source_a = "canon-a"
        source_b = "canon-b"
        ranked_a = self._ranked_source(source_a)
        ranked_b = self._ranked_source(source_b)
        evidence = EvidencePack(
            query=self._query(),
            sources=(ranked_a, ranked_b),
            fragments=(
                Fragment(source_a, "one_neko_punch", 0, 1, 2, "Kuro existe.", 1.0),
                Fragment(source_b, "one_neko_punch", 0, 3, 4, "Hitomi observa a Kuro.", 0.9),
            ),
            ranking_explanation=(),
            conflicts=(),
            omissions=(),
            confidence=self._confidence(),
            source_versions=((source_a, "v1"), (source_b, "v2")),
            coverage=self._coverage(),
        )
        return LocalExecution(
            text="resultado",
            searched=True,
            evidence=evidence,
            context=None,
            agent_result=None,
            rule_resolution=None,
            provider_response=None,
        )

    @staticmethod
    def _query():
        from bot_ia.librarian.models import RetrievalQuery
        return RetrievalQuery("Kuro Hitomi", "one_neko_punch")

    @staticmethod
    def _confidence():
        from bot_ia.contracts import Confidence
        return Confidence.HIGH

    @staticmethod
    def _coverage():
        from bot_ia.librarian.models import Coverage, CoverageStatus
        return Coverage(CoverageStatus.ESTABLISHED, 2, 2, 0)

    @staticmethod
    def _ranked_source(source_id: str):
        from bot_ia.contracts import AuthorityLevel, CanonStatus, EpistemicStatus, EvidenceStatus, SourceRecord, SourceStatus
        from bot_ia.librarian.models import CatalogEntry, RankedSource, SourceMetadata, SourceType
        record = SourceRecord(source_id=source_id, path=f"{source_id}.md", content_hash="hash")
        metadata = SourceMetadata(source_id=source_id, source_type=SourceType.CHAPTER, authority=AuthorityLevel.PRIMARY, status=SourceStatus.VALID, canon_status=CanonStatus.CANON)
        entry = CatalogEntry(record, metadata, "contenido", "hash")
        return RankedSource(entry, 1.0, 1.0, EvidenceStatus.SUPPORTED, EpistemicStatus.ESTABLISHED, ContextSelectionTests._confidence(), ())

    def test_lists_only_sources_retrieved_for_execution(self) -> None:
        execution = self._execution()
        self.assertEqual(available_context_sources(execution), ("canon-a", "canon-b"))

    def test_selection_filters_sources_fragments_and_versions(self) -> None:
        selected = select_context_sources(self._execution(), ("canon-b",))
        self.assertEqual(available_context_sources(selected), ("canon-b",))
        self.assertEqual(tuple(fragment.source_id for fragment in selected.evidence.fragments), ("canon-b",))
        self.assertEqual(selected.evidence.source_versions, (("canon-b", "v2"),))

    def test_unknown_source_is_rejected_without_new_retrieval(self) -> None:
        with self.assertRaises(ValueError):
            select_context_sources(self._execution(), ("not-retrieved",))

    def test_original_execution_is_not_mutated(self) -> None:
        execution = self._execution()
        select_context_sources(execution, ("canon-a",))
        self.assertEqual(available_context_sources(execution), ("canon-a", "canon-b"))


if __name__ == "__main__":
    unittest.main()
