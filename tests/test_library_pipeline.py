import unittest
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceRecord, SourceStatus
from bot_ia.librarian import EntityIndex, LocalLibrarian, RetrievalQuery, SourceInventory
from bot_ia.librarian.models import CatalogEntry, SourceMetadata, SourceType


class LibraryPipelineTests(unittest.TestCase):
    def test_inventory_discovers_docx_and_extracts_text(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            docx = tmp_path / "personajes.docx"
            xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Kuro</w:t></w:r></w:p>'
                '<w:p><w:r><w:t>Catgirl protagonista.</w:t></w:r></w:p></w:body></w:document>'
            ).encode("utf-8")
            with ZipFile(docx, "w") as archive:
                archive.writestr("word/document.xml", xml)
            entries = SourceInventory(tmp_path).discover("one_neko_punch")
            self.assertEqual(1, len(entries))
            self.assertIs(entries[0].metadata.source_type, SourceType.CHARACTER)
            self.assertIn("Kuro", entries[0].content)
            self.assertIn("Catgirl protagonista.", entries[0].content)

    def _character_entry(self):
        content = "# Personajes\n\n### Kuro\nProtagonista de One Neko Punch.\n\n### Anzu\nMentora.\n"
        version = sha256(content.encode("utf-8")).hexdigest()
        metadata = SourceMetadata("personajes", SourceType.CHARACTER, AuthorityLevel.INTERNAL_CANON, SourceStatus.VALIDATED, CanonStatus.CANON)
        record = SourceRecord("personajes", "one_neko_punch", metadata.source_type.value, metadata.authority, metadata.status, Path("personajes.md"), version, metadata.canon_status)
        return CatalogEntry(record, metadata, content, version)

    def test_flat_character_source_indexes_heading_entities(self):
        entry = self._character_entry()
        index = EntityIndex((entry,))
        self.assertEqual({"Kuro", "Anzu"}, {candidate.name for candidate in index.candidates})
        self.assertEqual((entry,), index.entries_for("kuro"))

    def test_librarian_identity_query_prefers_character_heading(self):
        entry = self._character_entry()
        evidence = LocalLibrarian().retrieve(RetrievalQuery("Kuro", "one_neko_punch"), (entry,))
        self.assertEqual("established", evidence.coverage.status.value)
        self.assertEqual("personajes", evidence.sources[0].entry.record.source_id)
        self.assertTrue(any("Kuro" in fragment.text for fragment in evidence.fragments))


if __name__ == "__main__":
    unittest.main()
