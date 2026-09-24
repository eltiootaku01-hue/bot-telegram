# -*- coding: utf-8 -*-
"""Cerebro local de Fase 2: produce expediente y decisión, sin generar prosa."""

from __future__ import annotations

import re

from bot_ia.contracts import Confidence, UniverseRegistry

from .intents import IntentClassifier, normalize_message
from .models import BrainRequest, BrainResult, Intent
from .references import ReferenceResolver


class LocalBrain:
    def __init__(self, registry: UniverseRegistry, classifier: IntentClassifier | None = None, reference_resolver: ReferenceResolver | None = None) -> None:
        self._registry = registry
        self._classifier = classifier or IntentClassifier()
        self._reference_resolver = reference_resolver or ReferenceResolver()

    def process(self, request: BrainRequest) -> BrainResult:
        normalized = normalize_message(request.message)
        intent = self._classifier.classify(normalized)
        universe_id = request.universe_id or (request.state.universe_id if request.state else None)
        state_status = "unchanged"
        requested_universe_id: str | None = None
        clarification: str | None = None

        if intent is Intent.UNIVERSE_CHANGE:
            requested_universe_id = self._requested_universe(normalized.normalized)
            if requested_universe_id is None:
                state_status, clarification = "rejected", "universe_not_specified"
            elif not self._registry.contains(requested_universe_id):
                state_status, clarification = "rejected", "unknown_universe"
            else:
                if request.state is not None:
                    request.state.universe_id = requested_universe_id
                    request.state.active_entity_ids = ()
                    request.state.recent_reference_ids = ()
                    request.state.chapter_id = None
                universe_id = requested_universe_id
                state_status = "updated"

        needs_universe = intent in {Intent.FACTUAL, Intent.CHARACTER, Intent.CANON, Intent.CONTINUITY, Intent.CREATIVE_WRITING, Intent.EDITORIAL_REVIEW, Intent.IDEA}
        if universe_id is None and needs_universe:
            clarification = "universe_required"

        references = ()
        if universe_id is not None:
            references = self._reference_resolver.resolve(normalized.normalized, universe_id, request.candidates, request.state)
            resolved_ids = tuple(dict.fromkeys(item.resolved_entity_id for item in references if item.resolved_entity_id is not None))
            if request.state is not None and not any(item.clarification_needed for item in references):
                request.state.recent_reference_ids = resolved_ids
                if resolved_ids:
                    request.state.active_entity_ids = resolved_ids

        ambiguous = clarification == "universe_required" or any(item.clarification_needed for item in references)
        if any(item.clarification_needed for item in references):
            clarification = "ambiguous_reference"
        confidence = Confidence.LOW if ambiguous or intent is Intent.UNKNOWN else Confidence.HIGH
        return BrainResult(normalized, intent, confidence, universe_id, references, ambiguous, clarification, request.state, state_status, requested_universe_id)

    def _requested_universe(self, text: str) -> str | None:
        for definition in self._registry.all():
            if re.search(r"(?<!\w)" + re.escape(definition.universe_id) + r"(?!\w)", text) or definition.display_name.casefold() in text:
                return definition.universe_id
        match = re.search(r"\b(?:universo|universe)\s+(?:a\s+|al\s+)?([a-z][a-z0-9_]*)", text)
        if match:
            return match.group(1)
        match = re.search(r"\bcambiar\s+a\s+([a-z][a-z0-9_]*)", text)
        return match.group(1) if match else None
