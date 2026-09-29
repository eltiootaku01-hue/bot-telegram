# -*- coding: utf-8 -*-
"""Core authority for canonical WebChat physical-resource ownership.

This module is intentionally backend-neutral. QWebEngine and Playwright do not
depend on it yet; later adapters may use the contracts defined here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import threading
import unicodedata
from typing import Optional


class PhysicalResourceState(str, Enum):
    AVAILABLE = "AVAILABLE"
    CLAIMING = "CLAIMING"
    BUSY = "BUSY"
    CANCELLING = "CANCELLING"
    RELEASING = "RELEASING"
    QUARANTINED = "QUARANTINED"


class PhysicalResourceIdentityError(ValueError):
    """Raised when a physical resource identity cannot be resolved safely."""


class PhysicalResourceClaimError(RuntimeError):
    """Raised when a physical resource cannot be claimed."""


class PhysicalResourceOwnershipError(RuntimeError):
    """Raised when a caller does not own the active claim."""


class PhysicalResourceStateError(RuntimeError):
    """Raised when a state transition violates the authority contract."""


@dataclass(frozen=True)
class PhysicalResourceDescriptor:
    """Canonical, backend-neutral identity of a physical WebChat surface."""

    provider: str
    authenticated_account_identity: str
    session_identity: str
    canonical_interaction_surface: str
    physical_resource_id: str

    @classmethod
    def resolve(
        cls,
        provider: str,
        authenticated_account_identity: str,
        session_identity: str,
        canonical_interaction_surface: str,
    ) -> "PhysicalResourceDescriptor":
        values = {
            "provider": _normalize_identity_part(provider),
            "authenticated_account_identity": _normalize_identity_part(
                authenticated_account_identity
            ),
            "session_identity": _normalize_identity_part(session_identity),
            "canonical_interaction_surface": _normalize_identity_part(
                canonical_interaction_surface
            ),
        }
        unresolved = [name for name, value in values.items() if not value]
        if unresolved:
            raise PhysicalResourceIdentityError(
                "UNRESOLVED_PHYSICAL_IDENTITY: " + ", ".join(unresolved)
            )

        canonical = json.dumps(
            values,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            **values,
            physical_resource_id=f"pwr-{digest}",
        )


@dataclass(frozen=True)
class PhysicalResourceSnapshot:
    """Read-only observation of one authority-managed resource."""

    physical_resource_id: str
    provider: str
    session_identity: str
    interaction_surface: str
    state: PhysicalResourceState
    owner: Optional[str]
    claim_id: Optional[str]
    execution_generation: Optional[int]
    backend: Optional[str]
    waitress_id: Optional[str]
    operation_id: Optional[str]
    created_at: datetime
    claimed_at: Optional[datetime]
    started_at: Optional[datetime]
    quarantine_reason: Optional[str]
    last_error: Optional[str]


@dataclass(frozen=True)
class PhysicalResourceClaim:
    """Opaque ownership identity returned by a successful claim."""

    physical_resource_id: str
    claim_id: str
    owner: str
    execution_generation: int


@dataclass
class _ResourceRecord:
    descriptor: PhysicalResourceDescriptor
    state: PhysicalResourceState
    owner: Optional[str]
    claim_id: Optional[str]
    execution_generation: Optional[int]
    backend: Optional[str]
    waitress_id: Optional[str]
    operation_id: Optional[str]
    created_at: datetime
    claimed_at: Optional[datetime]
    started_at: Optional[datetime]
    quarantine_reason: Optional[str]
    last_error: Optional[str]


def _normalize_identity_part(value: str) -> str:
    if not isinstance(value, str):
        raise PhysicalResourceIdentityError("IDENTITY_PART_MUST_BE_STRING")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.strip().split())
    return normalized.casefold()


class PhysicalWebChatResourceAuthority:
    """Thread-safe in-process owner of physical WebChat resource records.

    This authority deliberately does not create or control browsers, pages,
    QWebEngine objects, sessions, providers, schedulers, or GUI state.
    """

    def __init__(self, *, now_provider=None) -> None:
        self._lock = threading.RLock()
        self._resources: dict[str, _ResourceRecord] = {}
        self._now = now_provider or (lambda: datetime.now(timezone.utc))
        self._claim_counter = 0

    def resolve_resource(
        self,
        provider: str,
        authenticated_account_identity: str,
        session_identity: str,
        canonical_interaction_surface: str,
    ) -> PhysicalResourceDescriptor:
        descriptor = PhysicalResourceDescriptor.resolve(
            provider,
            authenticated_account_identity,
            session_identity,
            canonical_interaction_surface,
        )
        with self._lock:
            if descriptor.physical_resource_id not in self._resources:
                self._resources[descriptor.physical_resource_id] = _ResourceRecord(
                    descriptor=descriptor,
                    state=PhysicalResourceState.AVAILABLE,
                    owner=None,
                    claim_id=None,
                    execution_generation=None,
                    backend=None,
                    waitress_id=None,
                    operation_id=None,
                    created_at=self._now(),
                    claimed_at=None,
                    started_at=None,
                    quarantine_reason=None,
                    last_error=None,
                )
            return descriptor

    def claim(
        self,
        physical_resource_id: str,
        requester_identity: str,
    ) -> PhysicalResourceClaim:
        if not requester_identity:
            raise PhysicalResourceClaimError("OWNER_IDENTITY_REQUIRED")

        with self._lock:
            record = self._require_resource(physical_resource_id)
            if record.state is not PhysicalResourceState.AVAILABLE:
                raise PhysicalResourceClaimError(
                    f"RESOURCE_NOT_AVAILABLE:{record.state.value}"
                )

            self._claim_counter += 1
            claim_id = f"claim-{self._claim_counter}"
            generation = (record.execution_generation or 0) + 1

            record.state = PhysicalResourceState.CLAIMING
            record.owner = requester_identity
            record.claim_id = claim_id
            record.execution_generation = generation
            record.claimed_at = self._now()
            record.started_at = None
            record.backend = None
            record.waitress_id = None
            record.operation_id = None
            record.quarantine_reason = None
            record.last_error = None

            self._assert_invariants_locked(record)
            return PhysicalResourceClaim(
                physical_resource_id=physical_resource_id,
                claim_id=claim_id,
                owner=requester_identity,
                execution_generation=generation,
            )

    def begin_execution(
        self,
        claim: PhysicalResourceClaim,
        *,
        backend: Optional[str] = None,
        waitress_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> PhysicalResourceSnapshot:
        with self._lock:
            record = self._require_owned_record(claim)
            if record.state is not PhysicalResourceState.CLAIMING:
                raise PhysicalResourceStateError(
                    f"BEGIN_EXECUTION_INVALID_STATE:{record.state.value}"
                )
            record.state = PhysicalResourceState.BUSY
            record.started_at = self._now()
            record.backend = backend
            record.waitress_id = waitress_id
            record.operation_id = operation_id
            self._assert_invariants_locked(record)
            return self._snapshot_locked(record)

    def validate_execution(
        self,
        physical_resource_id: str,
        claim_id: str,
        execution_generation: int,
        *,
        operation_id: Optional[str] = None,
    ) -> bool:
        with self._lock:
            record = self._resources.get(physical_resource_id)
            if record is None:
                return False
            if record.state is not PhysicalResourceState.BUSY:
                return False
            if record.claim_id != claim_id:
                return False
            if record.execution_generation != execution_generation:
                return False
            if operation_id is not None and record.operation_id != operation_id:
                return False
            return True

    def release(self, claim: PhysicalResourceClaim) -> PhysicalResourceSnapshot:
        with self._lock:
            record = self._require_owned_record(claim)
            if record.state not in {
                PhysicalResourceState.CLAIMING,
                PhysicalResourceState.BUSY,
                PhysicalResourceState.CANCELLING,
                PhysicalResourceState.RELEASING,
            }:
                raise PhysicalResourceStateError(
                    f"RELEASE_INVALID_STATE:{record.state.value}"
                )
            record.state = PhysicalResourceState.RELEASING
            record.state = PhysicalResourceState.AVAILABLE
            record.owner = None
            record.claim_id = None
            record.backend = None
            record.waitress_id = None
            record.operation_id = None
            record.claimed_at = None
            record.started_at = None
            record.quarantine_reason = None
            record.last_error = None
            self._assert_invariants_locked(record)
            return self._snapshot_locked(record)

    def quarantine(
        self,
        claim: PhysicalResourceClaim,
        reason: str,
        *,
        evidence: Optional[str] = None,
    ) -> PhysicalResourceSnapshot:
        if not reason:
            raise ValueError("QUARANTINE_REASON_REQUIRED")

        with self._lock:
            record = self._require_owned_record(claim)
            if record.state is PhysicalResourceState.AVAILABLE:
                raise PhysicalResourceStateError("CANNOT_QUARANTINE_UNOWNED_RESOURCE")
            record.state = PhysicalResourceState.QUARANTINED
            record.quarantine_reason = reason
            record.last_error = evidence
            self._assert_invariants_locked(record)
            return self._snapshot_locked(record)

    def reconcile(
        self,
        physical_resource_id: str,
        *,
        evidence: str,
    ) -> PhysicalResourceSnapshot:
        if not evidence:
            raise ValueError("RECONCILIATION_EVIDENCE_REQUIRED")

        with self._lock:
            record = self._require_resource(physical_resource_id)
            if record.state is not PhysicalResourceState.QUARANTINED:
                raise PhysicalResourceStateError(
                    f"RECONCILE_INVALID_STATE:{record.state.value}"
                )
            record.state = PhysicalResourceState.AVAILABLE
            record.owner = None
            record.claim_id = None
            record.backend = None
            record.waitress_id = None
            record.operation_id = None
            record.claimed_at = None
            record.started_at = None
            record.quarantine_reason = None
            record.last_error = evidence
            self._assert_invariants_locked(record)
            return self._snapshot_locked(record)

    def snapshot(self, physical_resource_id: str) -> PhysicalResourceSnapshot:
        with self._lock:
            return self._snapshot_locked(self._require_resource(physical_resource_id))

    def snapshots(self) -> tuple[PhysicalResourceSnapshot, ...]:
        with self._lock:
            return tuple(
                self._snapshot_locked(record)
                for record in self._resources.values()
            )

    def _require_resource(self, physical_resource_id: str) -> _ResourceRecord:
        record = self._resources.get(physical_resource_id)
        if record is None:
            raise KeyError(f"UNKNOWN_PHYSICAL_RESOURCE:{physical_resource_id}")
        return record

    def _require_owned_record(
        self,
        claim: PhysicalResourceClaim,
    ) -> _ResourceRecord:
        record = self._require_resource(claim.physical_resource_id)
        if (
            record.claim_id != claim.claim_id
            or record.owner != claim.owner
            or record.execution_generation != claim.execution_generation
        ):
            raise PhysicalResourceOwnershipError("STALE_OR_FOREIGN_CLAIM")
        return record

    @staticmethod
    def _assert_invariants_locked(record: _ResourceRecord) -> None:
        if record.state is PhysicalResourceState.AVAILABLE:
            if any(
                value is not None
                for value in (
                    record.owner,
                    record.claim_id,
                    record.backend,
                    record.waitress_id,
                    record.operation_id,
                    record.claimed_at,
                    record.started_at,
                    record.quarantine_reason,
                )
            ):
                raise PhysicalResourceStateError(
                    "AVAILABLE_RESOURCE_HAS_ACTIVE_METADATA"
                )
        elif record.state is PhysicalResourceState.QUARANTINED:
            if not record.quarantine_reason:
                raise PhysicalResourceStateError(
                    "QUARANTINED_RESOURCE_REQUIRES_REASON"
                )
        else:
            if not record.owner or not record.claim_id:
                raise PhysicalResourceStateError(
                    "ACTIVE_RESOURCE_REQUIRES_OWNER_AND_CLAIM"
                )
            if record.execution_generation is None:
                raise PhysicalResourceStateError(
                    "ACTIVE_RESOURCE_REQUIRES_GENERATION"
                )

    def _snapshot_locked(
        self,
        record: _ResourceRecord,
    ) -> PhysicalResourceSnapshot:
        return PhysicalResourceSnapshot(
            physical_resource_id=record.descriptor.physical_resource_id,
            provider=record.descriptor.provider,
            session_identity=record.descriptor.session_identity,
            interaction_surface=record.descriptor.canonical_interaction_surface,
            state=record.state,
            owner=record.owner,
            claim_id=record.claim_id,
            execution_generation=record.execution_generation,
            backend=record.backend,
            waitress_id=record.waitress_id,
            operation_id=record.operation_id,
            created_at=record.created_at,
            claimed_at=record.claimed_at,
            started_at=record.started_at,
            quarantine_reason=record.quarantine_reason,
            last_error=record.last_error,
        )
