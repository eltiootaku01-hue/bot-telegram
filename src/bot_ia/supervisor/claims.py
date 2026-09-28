# -*- coding: utf-8 -*-
"""Contratos de claims enlazados a la evidencia del Supervisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .models import Confidence, utc_now, new_id
from .store import EvidenceStore


class ClaimStatus(str, Enum):
    OBSERVED = "OBSERVED"
    TESTED = "TESTED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


@dataclass(slots=True)
class Claim:
    claim_id: str
    statement: str
    status: ClaimStatus
    confidence: Confidence
    evidence_ids: list[str]
    source: str
    created_at: str
    updated_at: str
    scope: str
    task_id: str | None = None
    parent_claim_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        statement: str,
        source: str,
        scope: str,
        evidence_ids: list[str] | None = None,
        status: ClaimStatus = ClaimStatus.UNKNOWN,
        confidence: Confidence = Confidence.UNKNOWN,
        task_id: str | None = None,
        parent_claim_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Claim":
        now = utc_now()
        return cls(
            claim_id=new_id("claim"),
            statement=statement,
            status=status,
            confidence=confidence,
            evidence_ids=list(evidence_ids or []),
            source=source,
            created_at=now,
            updated_at=now,
            scope=scope,
            task_id=task_id,
            parent_claim_id=parent_claim_id,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["confidence"] = self.confidence.value
        return data


@dataclass(frozen=True, slots=True)
class ClaimValidation:
    claim_id: str
    evidence_exists: bool
    missing_evidence_ids: tuple[str, ...]
    valid_for_verified_confidence: bool

    @property
    def status(self) -> ClaimStatus:
        if not self.evidence_exists:
            return ClaimStatus.UNKNOWN
        if self.valid_for_verified_confidence:
            return ClaimStatus.TESTED
        return ClaimStatus.UNKNOWN


class ClaimStore:
    """Registro contractual en memoria; evidencia permanece en EvidenceStore."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self.evidence_store = evidence_store
        self._claims: dict[str, Claim] = {}

    def add(self, claim: Claim) -> Claim:
        self._claims[claim.claim_id] = claim
        return claim

    def get(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def list(self) -> list[Claim]:
        return list(self._claims.values())

    def link_evidence(self, claim_id: str, evidence_id: str) -> Claim:
        claim = self._require(claim_id)
        if self.evidence_store.get(evidence_id) is None:
            raise KeyError(f"unknown evidence_id: {evidence_id}")
        if evidence_id not in claim.evidence_ids:
            claim.evidence_ids.append(evidence_id)
        claim.updated_at = utc_now()
        return claim

    def set_status(self, claim_id: str, status: ClaimStatus) -> Claim:
        claim = self._require(claim_id)
        claim.status = ClaimStatus(status)
        claim.updated_at = utc_now()
        return claim

    def set_confidence(self, claim_id: str, confidence: Confidence) -> Claim:
        claim = self._require(claim_id)
        confidence = Confidence(confidence)
        if confidence is Confidence.VERIFIED:
            validation = self.validate(claim_id)
            if not validation.valid_for_verified_confidence:
                raise ValueError(
                    "VERIFIED claim requires existing evidence references"
                )
        claim.confidence = confidence
        claim.updated_at = utc_now()
        return claim

    def validate(self, claim_id: str) -> ClaimValidation:
        claim = self._require(claim_id)
        missing = tuple(
            evidence_id
            for evidence_id in claim.evidence_ids
            if self.evidence_store.get(evidence_id) is None
        )
        exists = bool(claim.evidence_ids) and not missing
        return ClaimValidation(
            claim_id=claim.claim_id,
            evidence_exists=exists,
            missing_evidence_ids=missing,
            valid_for_verified_confidence=exists,
        )

    def effective_confidence(self, claim_id: str) -> Confidence:
        claim = self._require(claim_id)
        validation = self.validate(claim_id)
        if claim.confidence is Confidence.VERIFIED and not validation.valid_for_verified_confidence:
            return Confidence.UNKNOWN
        return claim.confidence

    def _require(self, claim_id: str) -> Claim:
        claim = self.get(claim_id)
        if claim is None:
            raise KeyError(f"unknown claim_id: {claim_id}")
        return claim


__all__ = ["Claim", "ClaimStatus", "ClaimStore", "ClaimValidation"]
