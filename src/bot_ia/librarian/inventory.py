"""Descubrimiento seguro y reproducible de textos locales bajo demanda."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceRecord, SourceStatus
from .models import CatalogEntry, SourceMetadata, SourceType

_TEXT_SUFFIXES = frozenset({".md", ".txt", ".docx"})
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class SourceReadError(ValueError):
    pass


def classify_source_type(path: Path) -> SourceType:
    """Clasifica por carpetas o, si la biblioteca es plana, por nombre."""
    parts = tuple(part.casefold() for part in path.parts)
    label = path.stem.casefold().replace("_", " ").replace("-", " ")
    directory_rules = {
        "characters": SourceType.CHARACTER, "personajes": SourceType.CHARACTER,
        "chapters": SourceType.CHAPTER, "capitulos": SourceType.CHAPTER,
        "materials": SourceType.MATERIAL, "materiales": SourceType.MATERIAL,
        "outlines": SourceType.OUTLINE, "escaletas": SourceType.OUTLINE,
        "style": SourceType.STYLE, "estilo": SourceType.STYLE,
        "world": SourceType.INTERNAL_CANON, "mundo": SourceType.INTERNAL_CANON,
        "informacion": SourceType.EXTERNAL_RESEARCH,
    }
    for directory, source_type in directory_rules.items():
        if directory in parts:
            return source_type
    rules = (
        (("revisado", "revision", "draft", "borrador"), SourceType.PLANNING),
        (("chapter", "capitulo", "cap "), SourceType.CHAPTER),
        (("character", "personaje"), SourceType.CHARACTER),
        (("one neko punch",), SourceType.CHAPTER),
        (("canon",), SourceType.INTERNAL_CANON),
        (("planning", "planificacion", "plan "), SourceType.PLANNING),
        (("outline", "escaleta"), SourceType.OUTLINE),
        (("style", "estilo", "narrativa", "tecnicas"), SourceType.STYLE),
        (("one punch man", "opm"), SourceType.OPM_REFERENCE),
        (("research", "investigacion"), SourceType.EXTERNAL_RESEARCH),
        (("memory", "memoria"), SourceType.MEMORY),
        (("material",), SourceType.MATERIAL),
    )
    for terms, source_type in rules:
        if any(term in label for term in terms):
            return source_type
    return SourceType.UNKNOWN


def classify_source_metadata(relative: str, path: Path) -> tuple[AuthorityLevel, SourceStatus, CanonStatus]:
    """Clasifica autoridad/estado/canon también para bibliotecas planas."""
    parts = tuple(part.casefold() for part in Path(relative).parts)
    label = path.stem.casefold().replace("_", " ").replace("-", " ")
    if any(term in label for term in ("revisado", "revision", "draft", "borrador")):
        return AuthorityLevel.PLAN, SourceStatus.VALIDATED, CanonStatus.NON_CANON
    if "chapters" in parts or "capitulos" in parts or "one neko punch" in label:
        return AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON
    if "characters" in parts or "personajes" in parts or "world" in parts or "mundo" in parts:
        return AuthorityLevel.INTERNAL_CANON, SourceStatus.VALIDATED, CanonStatus.CANON
    if "one punch man" in label or "opm" in label:
        return AuthorityLevel.EXTERNAL_REFERENCE, SourceStatus.VALIDATED, CanonStatus.UNKNOWN
    if "research" in label or "investigacion" in label or "informacion" in parts:
        return AuthorityLevel.EXTERNAL_REFERENCE, SourceStatus.VALIDATED, CanonStatus.UNKNOWN
    if any(term in label for term in ("narrativa", "estilo", "tecnicas")):
        return AuthorityLevel.PLAN, SourceStatus.VALIDATED, CanonStatus.NON_CANON
    if any(directory in parts for directory in ("outlines", "materials", "escaletas", "materiales", "style", "estilo")):
        return AuthorityLevel.PLAN, SourceStatus.VALIDATED, CanonStatus.NON_CANON
    return AuthorityLevel.UNKNOWN, SourceStatus.PENDING, CanonStatus.UNKNOWN


class SourceInventory:
    def __init__(self, source_root: Path, *, max_file_bytes: int = 8 * 1024 * 1024) -> None:
        self._root = source_root.resolve()
        self._max_file_bytes = max_file_bytes

    def discover(self, universe_id: str, metadata_by_path: dict[str, SourceMetadata] | None = None) -> tuple[CatalogEntry, ...]:
        metadata_by_path = metadata_by_path or {}
        if not self._root.is_dir():
            raise SourceReadError("source root does not exist")
        entries: list[CatalogEntry] = []
        for path in sorted(self._root.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(self._root):
                raise SourceReadError("source path escapes inventory root")
            if resolved.stat().st_size > self._max_file_bytes:
                raise SourceReadError(f"source exceeds size limit: {resolved.name}")
            relative = resolved.relative_to(self._root).as_posix()
            metadata = metadata_by_path.get(relative) or self._default_metadata(relative, resolved)
            content = self._read(resolved)
            version = sha256(content.encode("utf-8")).hexdigest()
            record = SourceRecord(metadata.source_id, universe_id, metadata.source_type.value, metadata.authority, metadata.status, relative, version, metadata.canon_status, metadata.provenance)
            entries.append(CatalogEntry(record, metadata, content, version))
        return tuple(entries)

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return SourceInventory._read_docx(path) if path.suffix.casefold() == ".docx" else path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise SourceReadError(f"source is not UTF-8: {path.name}") from error

    @staticmethod
    def _read_docx(path: Path) -> str:
        """Extrae texto de DOCX con la biblioteca estándar, sin dependencia externa."""
        try:
            with ZipFile(path) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
        except (BadZipFile, KeyError, ElementTree.ParseError) as error:
            raise SourceReadError(f"source DOCX is invalid: {path.name}") from error
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{_W_NS}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{_W_NS}t"))
            if text.strip():
                paragraphs.append(text.strip())
        return "\n\n".join(paragraphs)

    @staticmethod
    def _default_metadata(relative: str, path: Path) -> SourceMetadata:
        source_id = relative.rsplit(".", 1)[0].replace("/", "__")
        source_type = classify_source_type(path)
        authority, status, canon_status = classify_source_metadata(relative, path)
        return SourceMetadata(source_id, source_type, authority, status, canon_status)
