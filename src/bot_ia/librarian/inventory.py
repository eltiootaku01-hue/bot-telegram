"""Descubrimiento seguro y reproducible de textos locales bajo demanda."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from bot_ia.contracts import (
    AuthorityLevel,
    CanonStatus,
    SourceRecord,
    SourceStatus,
)

from .models import CatalogEntry, SourceMetadata, SourceType

_TEXT_SUFFIXES = frozenset({".md", ".txt"})


class SourceReadError(ValueError):
    pass


def classify_source_type(path: Path) -> SourceType:
    """Clasifica el tipo por ruta y nombre."""
    parts = tuple(part.casefold() for part in path.parts)
    label = path.stem.casefold()

    directory_rules = {
        "characters": SourceType.CHARACTER,
        "chapters": SourceType.CHAPTER,
        "materials": SourceType.MATERIAL,
        "outlines": SourceType.OUTLINE,
        "style": SourceType.STYLE,
        "world": SourceType.INTERNAL_CANON,
    }

    for directory, source_type in directory_rules.items():
        if directory in parts:
            return source_type

    rules = (
        (("chapter", "capitulo"), SourceType.CHAPTER),
        (("character", "personaje"), SourceType.CHARACTER),
        (("canon",), SourceType.INTERNAL_CANON),
        (("planning", "planificacion", "plan_"), SourceType.PLANNING),
        (("outline", "escaleta"), SourceType.OUTLINE),
        (("style", "estilo"), SourceType.STYLE),
        (("one_punch_man", "one-punch-man", "opm"), SourceType.OPM_REFERENCE),
        (("research", "investigacion"), SourceType.EXTERNAL_RESEARCH),
        (("memory", "memoria"), SourceType.MEMORY),
        (("material",), SourceType.MATERIAL),
    )

    for terms, source_type in rules:
        if any(term in label for term in terms):
            return source_type

    return SourceType.UNKNOWN


def classify_source_metadata(
    relative: str,
    path: Path,
) -> tuple[AuthorityLevel, SourceStatus, CanonStatus]:
    """Clasifica autoridad, estado y canon según la ubicación de la fuente."""

    parts = tuple(part.casefold() for part in Path(relative).parts)
    label = path.stem.casefold()

    # Manuscrito propio: fuente primaria del proyecto.
    if "chapters" in parts:
        return (
            AuthorityLevel.PRIMARY,
            SourceStatus.VALIDATED,
            CanonStatus.CANON,
        )

    # Canon interno explícito del proyecto.
    if "world" in parts and any(
        part.startswith("canon-")
        for part in parts
    ):
        return (
            AuthorityLevel.INTERNAL_CANON,
            SourceStatus.VALIDATED,
            CanonStatus.CANON,
        )

    # Fichas de personajes del proyecto.
    if "characters" in parts:
        return (
            AuthorityLevel.INTERNAL_CANON,
            SourceStatus.VALIDATED,
            CanonStatus.CANON,
        )

    # Documento maestro / referencia específica de One Punch Man.
    if (
        "informacion" in parts
        and any(
            term in label
            for term in (
                "one_punch_man",
                "one-punch-man",
                "opm",
            )
        )
    ):
        return (
            AuthorityLevel.EXTERNAL_REFERENCE,
            SourceStatus.VALIDATED,
            CanonStatus.UNKNOWN,
        )

    # Investigación/referencia externa general.
    if "informacion" in parts:
        return (
            AuthorityLevel.EXTERNAL_REFERENCE,
            SourceStatus.VALIDATED,
            CanonStatus.UNKNOWN,
        )

    # Planificación y outlines no son hechos establecidos.
    if "outlines" in parts or "materials" in parts:
        return (
            AuthorityLevel.PLAN,
            SourceStatus.VALIDATED,
            CanonStatus.NON_CANON,
        )

    # Guías de estilo tampoco establecen hechos del mundo.
    if "style" in parts:
        return (
            AuthorityLevel.PLAN,
            SourceStatus.VALIDATED,
            CanonStatus.NON_CANON,
        )

    return (
        AuthorityLevel.UNKNOWN,
        SourceStatus.PENDING,
        CanonStatus.UNKNOWN,
    )


class SourceInventory:
    def __init__(
        self,
        source_root: Path,
        *,
        max_file_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self._root = source_root.resolve()
        self._max_file_bytes = max_file_bytes

    def discover(
        self,
        universe_id: str,
        metadata_by_path: dict[str, SourceMetadata] | None = None,
    ) -> tuple[CatalogEntry, ...]:
        metadata_by_path = metadata_by_path or {}

        if not self._root.is_dir():
            raise SourceReadError("source root does not exist")

        entries: list[CatalogEntry] = []

        for path in sorted(self._root.rglob("*")):
            if (
                not path.is_file()
                or path.suffix.casefold() not in _TEXT_SUFFIXES
            ):
                continue

            resolved = path.resolve()

            if not resolved.is_relative_to(self._root):
                raise SourceReadError(
                    "source path escapes inventory root"
                )

            if resolved.stat().st_size > self._max_file_bytes:
                raise SourceReadError(
                    f"source exceeds size limit: {resolved.name}"
                )

            relative = resolved.relative_to(self._root).as_posix()

            metadata = (
                metadata_by_path.get(relative)
                or self._default_metadata(relative, resolved)
            )

            content = self._read(resolved)
            version = sha256(
                content.encode("utf-8")
            ).hexdigest()

            record = SourceRecord(
                metadata.source_id,
                universe_id,
                metadata.source_type.value,
                metadata.authority,
                metadata.status,
                relative,
                version,
                metadata.canon_status,
                metadata.provenance,
            )

            entries.append(
                CatalogEntry(
                    record,
                    metadata,
                    content,
                    version,
                )
            )

        return tuple(entries)

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise SourceReadError(
                f"source is not UTF-8: {path.name}"
            ) from error

    @staticmethod
    def _default_metadata(relative: str, path: Path) -> SourceMetadata:
        source_id = relative.rsplit(".", 1)[0].replace("/", "__")
        source_type = classify_source_type(path)

        authority, status, canon_status = classify_source_metadata(
            relative,
            path,
        )

        return SourceMetadata(
            source_id,
            source_type,
            authority,
            status,
            canon_status,
        )