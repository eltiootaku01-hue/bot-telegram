from __future__ import annotations

import unittest
from pathlib import Path

from bot_ia.core.context_selection import available_context_sources, select_context_sources
from bot_ia.core.local_workflow import LocalExecution
from bot_ia.contracts import AuthorityLevel, CanonStatus, Confidence, EpistemicStatus, EvidenceStatus, SourceRecord, SourceStatus
from bot_ia.librarian.models import CatalogEntry, Coverage, CoverageStatus, EvidencePack, Fragment, RankedSource, RetrievalQuery, SourceMetadata, SourceType


class ContextSelectionTests(unittest.TestCase):
    def _execution(self) -> LocalExecution:
        source_a = "canon_a"
        source_b = "canon_b"
        evidence = EvidencePack(
            query=RetrievalQuery("Kuro Hitomi", "one_neko_punch"),
            sources=(self._ranked_source(source_a), self._ranked_source(source_b)),
            fragments=(
                Fragment(source_a, "one_neko_punch", 0, 1, 2, "Kuro existe.", 1.0),
                Fragment(source_b, "one_neko_punch", 0, 3, 4, "Hitomi observa a Kuro.", 0.9),
            ),
            ranking_explanation=(),
            conflicts=(),
            omissions=(),
            confidence=Confidence.HIGH,
            source_versions=((source_a, "v1"), (source_b, "v2")),
            coverage=Coverage(CoverageStatus.ESTABLISHED, 2, 2, 0),
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
    def _ranked_source(source_id: str) -> RankedSource:
        record = SourceRecord(
            source_id=source_id,
            universe_id="one_neko_punch",
            source_type="chapter",
            authority=AuthorityLevel.PRIMARY,
            status=SourceStatus.VALIDATED,
            path=Path(f"{source_id}.md"),
            content_hash="hash",
            canon_status=CanonStatus.CANON,
        )
        metadata = SourceMetadata(
            source_id=source_id,
            source_type=SourceType.CHAPTER,
            authority=AuthorityLevel.PRIMARY,
            status=SourceStatus.VALIDATED,
            canon_status=CanonStatus.CANON,
        )
        entry = CatalogEntry(record, metadata, "contenido", "hash")
        return RankedSource(entry, 1.0, 1.0, EvidenceStatus.FOUND, EpistemicStatus.ESTABLISHED, Confidence.HIGH, ())

    def test_lists_only_sources_retrieved_for_execution(self) -> None:
        self.assertEqual(available_context_sources(self._execution()), ("canon_a", "canon_b"))

    def test_selection_filters_sources_fragments_and_versions(self) -> None:
        selected = select_context_sources(self._execution(), ("canon_b",))
        self.assertEqual(available_context_sources(selected), ("canon_b",))
        self.assertEqual(tuple(fragment.source_id for fragment in selected.evidence.fragments), ("canon_b",))
        self.assertEqual(selected.evidence.source_versions, (("canon_b", "v2"),))

    def test_unknown_source_is_rejected_without_new_retrieval(self) -> None:
        with self.assertRaises(ValueError):
            select_context_sources(self._execution(), ("not_retrieved",))

    def test_original_execution_is_not_mutated(self) -> None:
        execution = self._execution()
        select_context_sources(execution, ("canon_a",))
        self.assertEqual(available_context_sources(execution), ("canon_a", "canon_b"))


if __name__ == "__main__":
    unittest.main()
