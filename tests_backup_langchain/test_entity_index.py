from pathlib import Path
import tempfile
import unittest

from bot_ia.librarian import EntityIndex, LocalLibrarian, RetrievalQuery, SourceInventory, SourceMetadata, SourceType
from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceStatus


class EntityIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def discover(self):
        entries = SourceInventory(self.root).discover(
            "one_neko_punch",
            {
                "na.md": SourceMetadata(
                    "char-na-maid-gata",
                    SourceType.CHARACTER,
                    AuthorityLevel.UNKNOWN,
                    SourceStatus.VALIDATED,
                    CanonStatus.UNKNOWN,
                ),
                "yume.md": SourceMetadata(
                    "char-entidad-gata-negra",
                    SourceType.CHARACTER,
                    AuthorityLevel.UNKNOWN,
                    SourceStatus.VALIDATED,
                    CanonStatus.UNKNOWN,
                ),
            },
        )
        return EntityIndex(entries)

    def test_multiline_alias_kuro_is_indexed(self) -> None:
        (self.root / "na.md").write_text(
            """---
id: char-na-maid-gata
type: character
name: "N/A"
aliases:
  - "Kuro (identidad pÃºblica accidental; planificaciÃ³n aprobada)"
---
# N/A
""",
            encoding="utf-8",
        )

        (self.root / "yume.md").write_text(
            """---
id: char-entidad-gata-negra
type: character
name: "Yume Kuro"
aliases:
  - Yume
  - "entidad gata negra"
---
# Yume Kuro
""",
            encoding="utf-8",
        )

        index = self.discover()

        kuro = [
            candidate
            for candidate in index.candidates
            if any(alias.casefold().startswith("kuro") for alias in candidate.aliases)
        ]

        self.assertEqual(1, len(kuro))
        self.assertEqual("char-na-maid-gata", kuro[0].entity_id)

    def test_multiline_alias_yume_is_indexed(self) -> None:
        (self.root / "na.md").write_text(
            """---
id: char-na-maid-gata
type: character
name: "N/A"
aliases:
  - "Kuro"
---
# N/A
""",
            encoding="utf-8",
        )

        (self.root / "yume.md").write_text(
            """---
id: char-entidad-gata-negra
type: character
name: "Yume Kuro"
aliases:
  - Yume
  - "entidad gata negra"
---
# Yume Kuro
""",
            encoding="utf-8",
        )

        index = self.discover()

        yume = [
            candidate
            for candidate in index.candidates
            if "Yume" in candidate.aliases
        ]

        self.assertEqual(1, len(yume))
        self.assertEqual("char-entidad-gata-negra", yume[0].entity_id)


if __name__ == "__main__":
    unittest.main()