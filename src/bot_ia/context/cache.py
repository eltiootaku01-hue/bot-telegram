"""Caché en memoria, aislada por universo y sin proceso residente."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json

from bot_ia.librarian.models import EvidencePack

from .models import CacheEntry, ContextPack


class CacheStatus(str, Enum):
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CacheLookup:
    status: CacheStatus
    entry: CacheEntry | None


def build_cache_key(evidence: EvidencePack, intent: str, algorithm_version: str) -> str:
    query = evidence.query
    payload = {
        "algorithm": algorithm_version,
        "arcs": query.allowed_arcs,
        "intent": intent,
        "max_spoiler": int(query.max_spoiler),
        "mediums": query.allowed_mediums,
        "query": " ".join(query.text.casefold().split()),
        "source_versions": evidence.source_versions,
        "universe": query.universe_id,
        "up_to_chapter": query.up_to_chapter,
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


class ContextCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    def get(self, key: str, now: datetime | None = None) -> CacheLookup:
        entry = self._entries.get(key)
        if entry is None:
            return CacheLookup(CacheStatus.MISS, None)
        instant = now or datetime.now(timezone.utc)
        if entry.expires_at is not None and instant >= entry.expires_at:
            del self._entries[key]
            return CacheLookup(CacheStatus.EXPIRED, None)
        return CacheLookup(CacheStatus.HIT, entry)

    def put(self, entry: CacheEntry) -> None:
        if entry.universe_id != entry.context.universe_id:
            raise ValueError("cache entry universe must match context universe")
        self._entries[entry.key] = entry

    def invalidate_source(self, source_id: str, current_version: str) -> int:
        stale = [key for key, entry in self._entries.items() if any(item_id == source_id and version != current_version for item_id, version in entry.source_versions)]
        for key in stale:
            del self._entries[key]
        return len(stale)
