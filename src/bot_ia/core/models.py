"""Contratos locales de procesamiento; no contienen adaptadores externos."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bot_ia.contracts import Confidence, SessionState


class Intent(str, Enum):
    GREETING = "greeting"
    HELP = "help"
    KNOWLEDGE_OVERVIEW = "knowledge_overview"
    FACTUAL = "factual"
    CHARACTER = "character"
    CANON = "canon"
    CONTINUITY = "continuity"
    IDEA = "idea"
    ORGANIZATION = "organization"
    CREATIVE_WRITING = "creative_writing"
    EDITORIAL_REVIEW = "editorial_review"
    EXTERNAL_RESEARCH = "external_research"
    UNIVERSE_CHANGE = "universe_change"
    CLARIFICATION_NEEDED = "clarification_needed"
    UNKNOWN = "unknown"


class Route(str, Enum):
    LOCAL = "local"
    SEARCH = "search"
    CLARIFICATION = "clarification"
    AGENT = "agent"
    LLM = "llm"


@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    original: str
    normalized: str
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    entity_id: str
    universe_id: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReferenceResolution:
    mention: str
    candidate_ids: tuple[str, ...]
    resolved_entity_id: str | None
    confidence: Confidence
    clarification_needed: bool = False


@dataclass(frozen=True, slots=True)
class BrainRequest:
    message: str
    user_id: str
    conversation_id: str
    state: SessionState | None
    universe_id: str | None = None
    candidates: tuple[EntityCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class BrainResult:
    normalized: NormalizedMessage
    intent: Intent
    confidence: Confidence
    universe_id: str | None
    references: tuple[ReferenceResolution, ...]
    ambiguity: bool
    clarification: str | None
    state: SessionState | None
    state_status: str
    requested_universe_id: str | None = None


@dataclass(frozen=True, slots=True)
class OllieGuide:
    task_type: str
    search_topics: tuple[str, ...] = ()
    source_hints: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    compact_request: str = ""
    escalate_to_api: bool = False


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: Route
    reason: str
    confidence: Confidence
    intent: Intent
    universe_id: str | None
    requires_search: bool = False
    requires_agent: bool = False
    requires_llm: bool = False
    clarification: str | None = None
    agent_id: str | None = None
