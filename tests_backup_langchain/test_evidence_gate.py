from pathlib import Path
import tempfile
import unittest

from bot_ia.contracts import (
    AuthorityLevel,
    CanonStatus,
    SourceStatus,
)
from bot_ia.core.evidence_gate import EvidenceGate
from bot_ia.librarian import (
    LocalLibrarian,
    RetrievalQuery,
    SourceInventory,
    SourceMetadata,
    SourceType,
)
from bot_ia.librarian.models import CoverageStatus


class EvidenceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_entries(
        self,
        *,
        content: str,
        section: str,
        authority: AuthorityLevel,
        canon_status: CanonStatus,
        source_type: SourceType = SourceType.CHAPTER,
        source_id: str = "source",
    ):
        (self.root / f"{source_id}.md").write_text(
            f"## {section}\n\n{content}",
            encoding="utf-8",
        )

        return SourceInventory(self.root).discover(
            "one_neko_punch",
            {
                f"{source_id}.md": SourceMetadata(
                    source_id,
                    source_type,
                    authority,
                    SourceStatus.VALIDATED,
                    canon_status,
                )
            },
        )

    def retrieve(self, entries, query: str = "Kuro"):
        return LocalLibrarian().retrieve(
            RetrievalQuery(query, "one_neko_punch"),
            entries,
        )

    def test_established_returns_evidence(self) -> None:
        entries = self.make_entries(
            content="Kuro protege la ciudad.",
            section="Hechos confirmados en manuscrito",
            authority=AuthorityLevel.PRIMARY,
            canon_status=CanonStatus.CANON,
        )

        pack = self.retrieve(entries)

        self.assertEqual(
            CoverageStatus.ESTABLISHED,
            pack.coverage.status,
        )

        result = EvidenceGate().build_factual_answer(pack)

        self.assertIn("Kuro protege la ciudad.", result)

    def test_not_established_does_not_claim_canon(self) -> None:
        entries = self.make_entries(
            content="Kuro está enamorado de X.",
            section="Relaciones futuras",
            authority=AuthorityLevel.UNKNOWN,
            canon_status=CanonStatus.UNKNOWN,
            source_type=SourceType.MATERIAL,
        )

        pack = self.retrieve(entries)

        self.assertEqual(
            CoverageStatus.NO_ESTABLECIDO,
            pack.coverage.status,
        )

        result = EvidenceGate().build_factual_answer(pack)

        self.assertIn(
            "No hay información establecida",
            result,
        )
        self.assertIn(
            "no confirma",
            result,
        )

    def test_no_match_is_explicit(self) -> None:
        entries = self.make_entries(
            content="Saitama aparece aquí.",
            section="Hechos confirmados en manuscrito",
            authority=AuthorityLevel.PRIMARY,
            canon_status=CanonStatus.CANON,
        )

        pack = self.retrieve(entries)

        self.assertEqual(
            CoverageStatus.NO_ENCONTRADO,
            pack.coverage.status,
        )

        result = EvidenceGate().build_factual_answer(pack)

        self.assertIn(
            "No encontré evidencia relevante",
            result,
        )

    def test_conflict_is_explicit(self) -> None:
        (self.root / "source_a.md").write_text(
            "## Hechos confirmados en manuscrito\n\nKuro protege la ciudad.",
            encoding="utf-8",
        )

        (self.root / "source_b.md").write_text(
            "## Hechos confirmados en manuscrito\n\nKuro abandona la ciudad.",
            encoding="utf-8",
        )

        metadata = {
            "source_a.md": SourceMetadata(
                "source_a",
                SourceType.CHAPTER,
                AuthorityLevel.PRIMARY,
                SourceStatus.VALIDATED,
                CanonStatus.CANON,
                conflict_key="kuro_location",
            ),
            "source_b.md": SourceMetadata(
                "source_b",
                SourceType.CHAPTER,
                AuthorityLevel.PRIMARY,
                SourceStatus.VALIDATED,
                CanonStatus.CANON,
                conflict_key="kuro_location",
            ),
        }

        entries = SourceInventory(self.root).discover(
            "one_neko_punch",
            metadata,
        )

        pack = self.retrieve(entries)

        self.assertEqual(
            CoverageStatus.CONFLICTO,
            pack.coverage.status,
        )

        result = EvidenceGate().build_factual_answer(pack)

        self.assertIn(
            "información en conflicto",
            result,
        )


if __name__ == "__main__":
    unittest.main()