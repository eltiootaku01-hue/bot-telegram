from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.identity import BotIdentity


class KnowledgeSourceKind(StrEnum):
    AUTHOR = "author"
    OPERATIONAL = "operational"
    EXTERNAL_GUIDELINE = "external_guideline"


@dataclass(frozen=True, slots=True)
class KnowledgeArticle:
    key: str
    identity: BotIdentity
    title: str
    keywords: tuple[str, ...]
    answer: str
    source: str
    source_kind: KnowledgeSourceKind
    priority: int = 0
    follow_up: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeAnswer:
    article: KnowledgeArticle
    score: int


@dataclass(frozen=True, slots=True)
class HandoffDecision:
    required: bool
    reason: str


__all__ = [
    "HandoffDecision",
    "KnowledgeAnswer",
    "KnowledgeArticle",
    "KnowledgeSourceKind",
]
