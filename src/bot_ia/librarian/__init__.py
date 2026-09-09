"""Bibliotecario local de Fase 3: inventario, retrieval y evidencia."""

from .entity_index import EntityIndex
from .inventory import SourceInventory, classify_source_type
from .models import (
    EvidencePack,
    RetrievalQuery,
    SourceMetadata,
    SourceType,
    SpoilerLevel,
    SpoilerScope,
    TemporalScope,
)
from .service import LocalLibrarian

__all__ = [
    "EntityIndex",
    "EvidencePack",
    "LocalLibrarian",
    "RetrievalQuery",
    "SourceInventory",
    "SourceMetadata",
    "SourceType",
    "SpoilerLevel",
    "SpoilerScope",
    "TemporalScope",
    "classify_source_type",
]