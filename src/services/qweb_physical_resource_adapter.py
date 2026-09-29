# -*- coding: utf-8 -*-
"""QWeb backend adapter for the shared physical WebChat authority.

The adapter translates QWeb lifecycle events into the backend-neutral
PhysicalWebChatResourceAuthority contract. It never derives physical identity
from a browser/page object, waitress id, resource key, or profile path.
"""

from __future__ import annotations

from dataclasses import dataclass

from bot_ia.core.physical_resource_authority import (
    PhysicalResourceClaim,
    PhysicalResourceDescriptor,
    PhysicalResourceSnapshot,
    PhysicalWebChatResourceAuthority,
)
from bot_ia.core.web_physical_identity import (
    AuthenticationState,
    canonicalize_interaction_surface,
)


class QWebPhysicalResourceError(RuntimeError):
    """Base error for QWeb physical-resource integration."""


class QWebPhysicalResourceIdentityError(QWebPhysicalResourceError):
    """Raised when QWeb has no explicit physical identity contract."""


@dataclass(frozen=True)
class QWebPhysicalExecution:
    """Immutable fencing tuple carried by one QWeb physical execution."""

    physical_resource_id: str
    claim_id: str
    execution_generation: int
    ticket_id: str
    operation_id: str


class QWebPhysicalResourceAdapter:
    """Translate QWeb lifecycle into the physical-resource authority."""

    BACKEND = "qweb"

    def __init__(
        self,
        authority: PhysicalWebChatResourceAuthority,
        descriptor: PhysicalResourceDescriptor,
        *,
        authentication_state: AuthenticationState = AuthenticationState.UNKNOWN,
        requester_identity: str = "qweb-worker",
    ) -> None:
        if not isinstance(authority, PhysicalWebChatResourceAuthority):
            raise TypeError("authority must be PhysicalWebChatResourceAuthority")
        if not isinstance(descriptor, PhysicalResourceDescriptor):
            raise QWebPhysicalResourceIdentityError(
                "EXPLICIT_PHYSICAL_RESOURCE_DESCRIPTOR_REQUIRED"
            )
        if not isinstance(requester_identity, str) or not requester_identity.strip():
            raise QWebPhysicalResourceError("REQUESTER_IDENTITY_REQUIRED")
        try:
            authentication_state = (
                authentication_state
                if isinstance(authentication_state, AuthenticationState)
                else AuthenticationState(str(authentication_state))
            )
        except ValueError as error:
            raise QWebPhysicalResourceIdentityError(
                "AUTHENTICATION_STATE_INVALID"
            ) from error

        self._authority = authority
        self._descriptor = descriptor
        self._authentication_state = authentication_state
        self._requester_identity = requester_identity.strip()

    @classmethod
    def resolve(
        cls,
        authority: PhysicalWebChatResourceAuthority,
        *,
        provider: str,
        authenticated_account_identity: str,
        session_identity: str,
        canonical_interaction_surface: str,
        authentication_state: AuthenticationState = AuthenticationState.UNKNOWN,
        requester_identity: str = "qweb-worker",
    ) -> "QWebPhysicalResourceAdapter":
        """Create an adapter only from explicit identity evidence."""
        descriptor = authority.resolve_resource(
            provider=provider,
            authenticated_account_identity=authenticated_account_identity,
            session_identity=session_identity,
            canonical_interaction_surface=canonical_interaction_surface,
        )
        return cls(
            authority,
            descriptor,
            authentication_state=authentication_state,
            requester_identity=requester_identity,
        )

    @property
    def descriptor(self) -> PhysicalResourceDescriptor:
        return self._descriptor

    @property
    def authority(self) -> PhysicalWebChatResourceAuthority:
        return self._authority

    def resolve_resource(self) -> PhysicalResourceDescriptor:
        return self._descriptor

    @property
    def authentication_state(self) -> AuthenticationState:
        return self._authentication_state

    def validate_interaction_surface(self, raw_url: str) -> bool:
        try:
            normalized = canonicalize_interaction_surface(raw_url)
        except Exception:
            return False
        return normalized == self._descriptor.canonical_interaction_surface

    def claim_resource(self) -> PhysicalResourceClaim:
        if self._authentication_state is not AuthenticationState.VERIFIED:
            raise QWebPhysicalResourceIdentityError(
                "PHYSICAL_EXECUTION_REQUIRES_VERIFIED_AUTHENTICATION:"
                f"{self._authentication_state.value}"
            )
        return self._authority.claim(
            self._descriptor.physical_resource_id,
            self._requester_identity,
        )

    def release_claim(
        self,
        claim: PhysicalResourceClaim,
        *,
        evidence: str,
    ) -> PhysicalResourceSnapshot:
        """Release a claim that never reached physical execution."""
        if not evidence.strip():
            raise QWebPhysicalResourceError("CLAIM_RELEASE_EVIDENCE_REQUIRED")
        return self._authority.release(claim)

    def quarantine_claim(
        self,
        claim: PhysicalResourceClaim,
        *,
        reason: str,
        evidence: str | None = None,
    ) -> PhysicalResourceSnapshot:
        return self._authority.quarantine(
            claim,
            reason,
            evidence=evidence,
        )

    def begin_execution(
        self,
        claim: PhysicalResourceClaim,
        *,
        ticket_id: str,
        operation_id: str,
    ) -> QWebPhysicalExecution:
        if not ticket_id.strip():
            raise QWebPhysicalResourceError("TICKET_ID_REQUIRED")
        if not operation_id.strip():
            raise QWebPhysicalResourceError("OPERATION_ID_REQUIRED")

        self._authority.begin_execution(
            claim,
            backend=self.BACKEND,
            operation_id=operation_id,
        )
        return QWebPhysicalExecution(
            physical_resource_id=claim.physical_resource_id,
            claim_id=claim.claim_id,
            execution_generation=claim.execution_generation,
            ticket_id=ticket_id,
            operation_id=operation_id,
        )

    def validate_execution(
        self,
        execution: QWebPhysicalExecution,
    ) -> bool:
        return self._authority.validate_execution(
            execution.physical_resource_id,
            execution.claim_id,
            execution.execution_generation,
            operation_id=execution.operation_id,
        )

    def validate_callback(
        self,
        execution: QWebPhysicalExecution,
        *,
        ticket_id: str,
    ) -> bool:
        """Fence a QWeb callback before it can mutate ticket state."""
        if ticket_id != execution.ticket_id:
            return False
        return self.validate_execution(execution)

    def request_cancel(
        self,
        execution: QWebPhysicalExecution,
    ) -> PhysicalResourceSnapshot:
        claim = PhysicalResourceClaim(
            physical_resource_id=execution.physical_resource_id,
            claim_id=execution.claim_id,
            owner=self._requester_identity,
            execution_generation=execution.execution_generation,
        )
        return self._authority.request_cancel(claim)

    def confirm_termination(
        self,
        execution: QWebPhysicalExecution,
        *,
        evidence: str,
    ) -> PhysicalResourceSnapshot:
        if not evidence.strip():
            raise QWebPhysicalResourceError("TERMINATION_EVIDENCE_REQUIRED")
        claim = self._claim_for_execution(execution)
        return self._authority.release(claim)

    def release_resource(
        self,
        execution: QWebPhysicalExecution,
        *,
        evidence: str,
    ) -> PhysicalResourceSnapshot:
        return self.confirm_termination(execution, evidence=evidence)

    def quarantine_resource(
        self,
        execution: QWebPhysicalExecution,
        *,
        reason: str,
        evidence: str | None = None,
    ) -> PhysicalResourceSnapshot:
        claim = self._claim_for_execution(execution)
        return self._authority.quarantine(
            claim,
            reason,
            evidence=evidence,
        )

    def snapshot(self) -> PhysicalResourceSnapshot:
        return self._authority.snapshot(
            self._descriptor.physical_resource_id,
        )

    def _claim_for_execution(
        self,
        execution: QWebPhysicalExecution,
    ) -> PhysicalResourceClaim:
        return PhysicalResourceClaim(
            physical_resource_id=execution.physical_resource_id,
            claim_id=execution.claim_id,
            owner=self._requester_identity,
            execution_generation=execution.execution_generation,
        )


__all__ = [
    "QWebPhysicalExecution",
    "QWebPhysicalResourceAdapter",
    "QWebPhysicalResourceError",
    "QWebPhysicalResourceIdentityError",
]
