"""Contratos pequeños para contexto futuro, sin proveedores ni persistencia."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bot_ia.contracts import Confidence


@dataclass(frozen=True, slots=True)
class TokenBudget:
    max_tokens: int
    reserved_tokens: int = 0
    chars_per_token: int = 4

    def __post_init__(self) -> None:
        if self.max_tokens < 1 or self.reserved_tokens < 0 or self.reserved_tokens >= self.max_tokens or self.chars_per_token < 1:
            raise ValueError("invalid token budget")

    @property
    def context_tokens(self) -> int:
        return self.max_tokens - self.reserved_tokens

    @property
    def max_chars(self) -> int:
        return self.context_tokens * self.chars_per_token


@dataclass(frozen=True, slots=True)
class ContextSelection:
    kind: str
    text: str
    source_id: str | None
    fragment_ordinal: int | None
    priority: float
    reason: str
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class ContextPack:
    universe_id: str
    selections: tuple[ContextSelection, ...]
    text: str
    estimated_tokens: int
    budget: TokenBudget
    sufficient: bool
    excessive: bool
    omissions: tuple[str, ...]
    source_versions: tuple[tuple[str, str], ...]
    confidence: Confidence
    algorithm_version: str


@dataclass(frozen=True, slots=True)
class CacheEntry:
    key: str
    universe_id: str
    context: ContextPack
    source_versions: tuple[tuple[str, str], ...]
    created_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResponseTrace:
    request_id: str
    universe_id: str
    intent: str
    route: str
    source_ids: tuple[str, ...]
    source_versions: tuple[tuple[str, str], ...]
    fragments_used: tuple[tuple[str, int], ...]
    ranking_reasons: tuple[str, ...]
    context_omissions: tuple[str, ...]
    cache_status: str
    uncertainty: str | None
