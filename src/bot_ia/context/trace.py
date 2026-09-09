"""Trazabilidad mínima: sólo identificadores, versiones y decisiones."""

from __future__ import annotations

from bot_ia.librarian.models import EvidencePack

from .models import ContextPack, ResponseTrace


def build_trace(request_id: str, intent: str, route: str, evidence: EvidencePack, context: ContextPack, cache_status: str) -> ResponseTrace:
    source_ids = tuple(item.source_id for item in context.selections if item.source_id is not None)
    fragments = tuple((item.source_id, item.fragment_ordinal) for item in context.selections if item.source_id is not None and item.fragment_ordinal is not None)
    reasons = tuple(reason for ranked in evidence.sources for reason in ranked.reasons)
    uncertainty = None if context.sufficient and not evidence.conflicts else evidence.coverage.status.value
    return ResponseTrace(request_id, context.universe_id, intent, route, source_ids, context.source_versions, fragments, reasons, context.omissions, cache_status, uncertainty)
