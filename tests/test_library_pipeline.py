from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceRecord, SourceStatus
from bot_ia.librarian import EntityIndex, LocalLibrarian, RetrievalQuery, SourceInventory
from bot_ia.librarian.models import CatalogEntry, SourceMetadata, SourceType


def test_inventory_discovers_docx_and_extracts_text(tmp_path):
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

    assert len(entries) == 1
    assert entries[0].metadata.source_type is SourceType.CHARACTER
    assert "Kuro" in entries[0].content
    assert "Catgirl protagonista." in entries[0].content


def test_flat_character_source_indexes_heading_entities():
    content = "# Personajes\n\n### Kuro\nProtagonista.\n\n### Anzu\nMentora.\n"
    version = sha256(content.encode("utf-8")).hexdigest()
    metadata = SourceMetadata(
        "personajes",
        SourceType.CHARACTER,
        AuthorityLevel.INTERNAL_CANON,
        SourceStatus.VALIDATED,
        CanonStatus.CANON,
    )
    record = SourceRecord(
        "personajes",
        "one_neko_punch",
        metadata.source_type.value,
        metadata.authority,
        metadata.status,
        Path("personajes.md"),
        version,
        metadata.canon_status,
    )
    entry = CatalogEntry(record, metadata, content, version)
    index = EntityIndex((entry,))

    assert {candidate.name for candidate in index.candidates} == {"Kuro", "Anzu"}
    assert index.entries_for("kuro") == (entry,)


def test_librarian_identity_query_prefers_character_heading():
    content = "# Personajes\n\n### Kuro\nProtagonista de One Neko Punch.\n\n### Anzu\nMentora.\n"
    version = sha256(content.encode("utf-8")).hexdigest()
    metadata = SourceMetadata(
        "personajes",
        SourceType.CHARACTER,
        AuthorityLevel.INTERNAL_CANON,
        SourceStatus.VALIDATED,
        CanonStatus.CANON,
    )
    record = SourceRecord(
        "personajes",
        "one_neko_punch",
        metadata.source_type.value,
        metadata.authority,
        metadata.status,
        Path("personajes.md"),
        version,
        metadata.canon_status,
    )
    entry = CatalogEntry(record, metadata, content, version)
    evidence = LocalLibrarian().retrieve(
        RetrievalQuery("Kuro", "one_neko_punch"),
        (entry,),
    )

    assert evidence.coverage.status.value == "established"
    assert evidence.sources[0].entry.record.source_id == "personajes"
    assert any("Kuro" in fragment.text for fragment in evidence.fragments)
