from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceStatus
from bot_ia.librarian import LocalLibrarian, RetrievalQuery, SourceInventory, SourceMetadata, SourceType, SpoilerLevel, SpoilerScope, TemporalScope, classify_source_type
from bot_ia.librarian.models import CoverageStatus


class Phase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "chapter_01.md").write_text("Kuro protege la ciudad.\n\nHitomi observa a Kuro.", encoding="utf-8")
        (self.root / "plan_future.md").write_text("Kuro viajara al norte.", encoding="utf-8")
        (self.root / "opm_reference.txt").write_text("Kuro tiene una referencia OPM.", encoding="utf-8")
        self.metadata = {
            "chapter_01.md": SourceMetadata("chapter_01", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON, TemporalScope("manga", "inicio", 1, 1), SpoilerScope(SpoilerLevel.NONE)),
            "plan_future.md": SourceMetadata("plan_future", SourceType.PLANNING, AuthorityLevel.PLAN, SourceStatus.VALIDATED, CanonStatus.PLANNING, TemporalScope("manga", "future", 8, 8), SpoilerScope(SpoilerLevel.HIGH)),
            "opm_reference.txt": SourceMetadata("opm_reference", SourceType.OPM_REFERENCE, AuthorityLevel.EXTERNAL_REFERENCE, SourceStatus.VALIDATED, CanonStatus.EXTERNAL, TemporalScope("opm", "external"), SpoilerScope(SpoilerLevel.LOW)),
        }
        self.entries = SourceInventory(self.root).discover("one_neko_punch", self.metadata)
        self.librarian = LocalLibrarian()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def retrieve(self, text: str, **kwargs: object):
        return self.librarian.retrieve(RetrievalQuery(text, "one_neko_punch", **kwargs), self.entries)

    def test_discovers_sources_and_versions(self) -> None:
        self.assertEqual(3, len(self.entries))
        self.assertTrue(all(len(entry.version) == 64 for entry in self.entries))

    def test_filters_by_universe(self) -> None:
        pack = self.librarian.retrieve(RetrievalQuery("Kuro", "other_world"), self.entries)
        self.assertEqual(CoverageStatus.NO_ENCONTRADO, pack.coverage.status)
        self.assertEqual(0, len(pack.sources))

    def test_identifies_source_type_without_assigning_canon(self) -> None:
        self.assertEqual(SourceType.CHAPTER, classify_source_type(Path("chapter_9.md")))
        default = SourceInventory(self.root).discover("one_neko_punch")[0]
        self.assertEqual(AuthorityLevel.UNKNOWN, default.record.authority)
        self.assertEqual(CanonStatus.UNKNOWN, default.record.canon_status)

    def test_classifies_source_type_from_directory(self) -> None:
        self.assertEqual(
            SourceType.CHARACTER,
            classify_source_type(Path("characters/005.saito.md")),
        )
        self.assertEqual(
            SourceType.CHAPTER,
            classify_source_type(Path("chapters/003.companeros-de-cuarto.md")),
        )
        self.assertEqual(
            SourceType.MATERIAL,
            classify_source_type(Path("materials/estado-del-proyecto.md")),
        )
        self.assertEqual(
            SourceType.INTERNAL_CANON,
            classify_source_type(Path("world/canon-one-neko-punch.md")),
        )
    def test_shown_chapter_ranks_above_planning(self) -> None:
        pack = self.retrieve("Kuro")
        self.assertEqual("chapter_01", pack.sources[0].entry.record.source_id)
        self.assertEqual(CoverageStatus.ESTABLISHED, pack.coverage.status)

    def test_authority_is_part_of_ranking(self) -> None:
        pack = self.retrieve("Kuro")
        chapter = next(item for item in pack.sources if item.entry.record.source_id == "chapter_01")
        plan = next(item for item in pack.sources if item.entry.record.source_id == "plan_future")
        self.assertGreater(chapter.score, plan.score)

    def test_extracts_small_relevant_fragments(self) -> None:
        pack = self.retrieve("Hitomi")
        self.assertEqual(1, len(pack.fragments))
        self.assertIn("Hitomi", pack.fragments[0].text)
        self.assertNotIn("protege", pack.fragments[0].text)

    def test_evidence_pack_is_reproducible(self) -> None:
        first, second = self.retrieve("Kuro"), self.retrieve("Kuro")
        self.assertEqual(first, second)
        self.assertTrue(first.source_versions)

    def test_detects_basic_conflict(self) -> None:
        (self.root / "chapter_conflict.md").write_text("Kuro abandona la ciudad.", encoding="utf-8")
        metadata = dict(self.metadata)
        metadata["chapter_01.md"] = SourceMetadata("chapter_01", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON, conflict_key="kuro_location")
        metadata["chapter_conflict.md"] = SourceMetadata("chapter_conflict", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON, conflict_key="kuro_location")
        entries = SourceInventory(self.root).discover("one_neko_punch", metadata)
        pack = self.librarian.retrieve(RetrievalQuery("Kuro", "one_neko_punch"), entries)
        self.assertEqual(CoverageStatus.CONFLICTO, pack.coverage.status)
        self.assertEqual("kuro_location", pack.conflicts[0].conflict_key)

    def test_planning_is_not_established(self) -> None:
        pack = self.retrieve("viajara")
        self.assertEqual(CoverageStatus.NO_ESTABLECIDO, pack.coverage.status)
        self.assertIn("NO_ESTABLECIDO", pack.omissions)

    def test_superseded_source_is_not_established(self) -> None:
        metadata = dict(self.metadata)
        metadata["chapter_01.md"] = SourceMetadata("chapter_01", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.SUPERSEDED, CanonStatus.CANON)
        entries = SourceInventory(self.root).discover("one_neko_punch", metadata)
        pack = self.librarian.retrieve(RetrievalQuery("protege", "one_neko_punch"), entries)
        self.assertEqual(CoverageStatus.NO_ESTABLECIDO, pack.coverage.status)

    def test_temporal_filter_excludes_future_chapter(self) -> None:
        pack = self.retrieve("viajara", up_to_chapter=1)
        self.assertEqual(CoverageStatus.NO_ENCONTRADO, pack.coverage.status)
        self.assertEqual(1, pack.coverage.filtered_count)

    def test_spoiler_filter_excludes_high_spoiler_source(self) -> None:
        pack = self.retrieve("viajara", max_spoiler=SpoilerLevel.LOW)
        self.assertEqual(CoverageStatus.NO_ENCONTRADO, pack.coverage.status)
        self.assertEqual(1, pack.coverage.filtered_count)

    def test_medium_filter_excludes_external_reference(self) -> None:
        pack = self.retrieve("referencia", allowed_mediums=("manga",))
        self.assertEqual(CoverageStatus.NO_ENCONTRADO, pack.coverage.status)

    def test_hash_changes_when_source_content_changes(self) -> None:
        first = next(item for item in self.entries if item.record.source_id == "chapter_01")
        (self.root / "chapter_01.md").write_text("Kuro cambia.", encoding="utf-8")
        second = next(item for item in SourceInventory(self.root).discover("one_neko_punch", self.metadata) if item.record.source_id == "chapter_01")
        self.assertNotEqual(first.version, second.version)

    def test_no_match_reports_no_encontrado(self) -> None:
        pack = self.retrieve("entidad inexistente")
        self.assertEqual(CoverageStatus.NO_ENCONTRADO, pack.coverage.status)
        self.assertIn("NO_ENCONTRADO", pack.omissions)


if __name__ == "__main__":
    unittest.main()
