"""Contratos reproducibles del Bibliotecario; no contienen E/S externa."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from bot_ia.contracts import AuthorityLevel, CanonStatus, Confidence, EpistemicStatus, EvidenceStatus, SourceRecord, SourceStatus


class SourceType(str, Enum):
    CHAPTER = "chapter"
    CHARACTER = "character"
    INTERNAL_CANON = "internal_canon"
    PLANNING = "planning"
    OUTLINE = "outline"
    MATERIAL = "material"
    STYLE = "style"
    OPM_REFERENCE = "opm_reference"
    EXTERNAL_RESEARCH = "external_research"
    MEMORY = "memory"
    UNKNOWN = "unknown"


class SpoilerLevel(int, Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    ALL = 4


class CoverageStatus(str, Enum):
    ESTABLISHED = "established"
    NO_ENCONTRADO = "no_encontrado"
    NO_ESTABLECIDO = "no_establecido"
    CONFLICTO = "conflicto"


@dataclass(frozen=True, slots=True)
class TemporalScope:
    medium: str | None = None
    arc: str | None = None
    chapter_start: int | None = None
    chapter_end: int | None = None
    narrative_time: str | None = None


@dataclass(frozen=True, slots=True)
class SpoilerScope:
    level: SpoilerLevel = SpoilerLevel.NONE
    medium: str | None = None
    arc: str | None = None
    chapter_start: int | None = None
    chapter_end: int | None = None
    narrative_time: str | None = None


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    source_id: str
    source_type: SourceType = SourceType.UNKNOWN
    authority: AuthorityLevel = AuthorityLevel.UNKNOWN
    status: SourceStatus = SourceStatus.PENDING
    canon_status: CanonStatus = CanonStatus.UNKNOWN
    temporal: TemporalScope = field(default_factory=TemporalScope)
    spoiler: SpoilerScope = field(default_factory=SpoilerScope)
    conflict_key: str | None = None
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    record: SourceRecord
    metadata: SourceMetadata
    content: str
    version: str

    def __post_init__(self) -> None:
        if self.record.source_id != self.metadata.source_id:
            raise ValueError("record and metadata source_id must match")
        if self.record.content_hash != self.version:
            raise ValueError("version must equal the record content hash")


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    text: str
    universe_id: str
    max_spoiler: SpoilerLevel = SpoilerLevel.ALL
    allowed_mediums: tuple[str, ...] = ()
    allowed_arcs: tuple[str, ...] = ()
    up_to_chapter: int | None = None
    max_fragments: int = 5
    preferred_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip() or not self.universe_id:
            raise ValueError("text and universe_id are required")
        if self.max_fragments < 1:
            raise ValueError("max_fragments must be positive")


@dataclass(frozen=True, slots=True)
class Fragment:
    source_id: str
    universe_id: str
    ordinal: int
    start_line: int
    end_line: int
    text: str
    lexical_score: float
    section: str = ""


@dataclass(frozen=True, slots=True)
class RankedSource:
    entry: CatalogEntry
    score: float
    relevance: float
    evidence: EvidenceStatus
    epistemic: EpistemicStatus
    confidence: Confidence
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    conflict_key: str
    source_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class Coverage:
    status: CoverageStatus
    candidate_count: int
    matched_count: int
    filtered_count: int


@dataclass(frozen=True, slots=True)
class EvidencePack:
    query: RetrievalQuery
    sources: tuple[RankedSource, ...]
    fragments: tuple[Fragment, ...]
    ranking_explanation: tuple[str, ...]
    conflicts: tuple[EvidenceConflict, ...]
    omissions: tuple[str, ...]
    confidence: Confidence
    source_versions: tuple[tuple[str, str], ...]
    coverage: Coverage

