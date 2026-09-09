"""Políticas explícitas que separan canon, evidencia y conocimiento."""

from __future__ import annotations

from dataclasses import dataclass

from bot_ia.contracts.models import AuthorityLevel, CanonStatus, Confidence, EpistemicStatus, EvidenceStatus, SourceRecord, SourceStatus


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    canon: CanonStatus
    evidence: EvidenceStatus
    epistemic: EpistemicStatus
    confidence: Confidence
    reason: str


def evaluate_authority(source: SourceRecord) -> AuthorityDecision:
    """Apply conservative deterministic policy; it never invents missing facts."""
    if source.status is SourceStatus.REJECTED:
        return AuthorityDecision(CanonStatus.NON_CANON, EvidenceStatus.NOT_FOUND, EpistemicStatus.NOT_FOUND, Confidence.NONE, "source rejected")
    if source.status is SourceStatus.CONFLICTED:
        return AuthorityDecision(CanonStatus.CONFLICTED, EvidenceStatus.CONFLICT, EpistemicStatus.CONFLICT, Confidence.LOW, "source marked conflicted")
    if source.status is not SourceStatus.VALIDATED:
        return AuthorityDecision(source.canon_status, EvidenceStatus.UNVERIFIED, EpistemicStatus.NOT_ESTABLISHED, Confidence.LOW, "source is not validated")
    if source.authority is AuthorityLevel.PLAN:
        return AuthorityDecision(CanonStatus.PLANNING, EvidenceStatus.FOUND, EpistemicStatus.NOT_ESTABLISHED, Confidence.MEDIUM, "planning is not a canonical fact")
    if source.authority is AuthorityLevel.EXTERNAL_REFERENCE:
        return AuthorityDecision(CanonStatus.EXTERNAL, EvidenceStatus.FOUND, EpistemicStatus.NOT_ESTABLISHED, Confidence.MEDIUM, "external reference is not internal canon")
    if source.authority in (AuthorityLevel.PRIMARY, AuthorityLevel.INTERNAL_CANON):
        return AuthorityDecision(CanonStatus.CANON, EvidenceStatus.FOUND, EpistemicStatus.ESTABLISHED, Confidence.HIGH, "validated internal evidence")
    if source.authority is AuthorityLevel.AUTHORIAL_DECISION:
        return AuthorityDecision(CanonStatus.CANON, EvidenceStatus.FOUND, EpistemicStatus.ESTABLISHED, Confidence.HIGH, "validated authorial decision")
    return AuthorityDecision(CanonStatus.UNKNOWN, EvidenceStatus.AMBIGUOUS, EpistemicStatus.AMBIGUOUS, Confidence.LOW, "authority unknown")
