# -*- coding: utf-8 -*-
"""Playwright backend adapter for the shared physical WebChat authority."""

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
    WebPhysicalIdentity,
    WebPhysicalIdentityRegistry,
    canonicalize_interaction_surface,
)
from bot_ia.core.web_queue import WebQueueManager


class PlaywrightPhysicalResourceError(RuntimeError):
    """Base error for Playwright physical-resource integration."""


class PlaywrightPhysicalResourceIdentityError(
    PlaywrightPhysicalResourceError
):
    """Raised when Playwright lacks a valid physical identity contract."""


class PlaywrightPhysicalResourceExecutionError(
    PlaywrightPhysicalResourceError
):
    """Raised when a Playwright execution is stale or unusable."""


@dataclass(frozen=True)
class PlaywrightPhysicalExecution:
    """Immutable fencing tuple carried by one Playwright execution."""

    physical_resource_id: str
    claim_id: str
    execution_generation: int
    ticket_id: str
    operation_id: str
    waitress_id: str


class PlaywrightPhysicalResourceAdapter:
    """Translate Playwright lifecycle into physical-resource authority."""

    BACKEND = "playwright"

    def __init__(
        self,
        authority: PhysicalWebChatResourceAuthority,
        descriptor: PhysicalResourceDescriptor,
        backend: WebQueueManager,
        *,
        authentication_state: AuthenticationState = AuthenticationState.UNKNOWN,
        requester_identity: str = "playwright-worker",
    ) -> None:
        if not isinstance(
            authority,
            PhysicalWebChatResourceAuthority,
        ):
            raise TypeError(
                "authority must be PhysicalWebChatResourceAuthority"
            )
        if not isinstance(descriptor, PhysicalResourceDescriptor):
            raise PlaywrightPhysicalResourceIdentityError(
                "EXPLICIT_PHYSICAL_RESOURCE_DESCRIPTOR_REQUIRED"
            )
        if not isinstance(backend, WebQueueManager):
            raise TypeError("backend must be WebQueueManager")
        if not isinstance(
            requester_identity,
            str,
        ) or not requester_identity.strip():
            raise PlaywrightPhysicalResourceError(
                "REQUESTER_IDENTITY_REQUIRED"
            )

        try:
            authentication_state = (
                authentication_state
                if isinstance(authentication_state, AuthenticationState)
                else AuthenticationState(str(authentication_state))
            )
        except ValueError as error:
            raise PlaywrightPhysicalResourceIdentityError(
                "AUTHENTICATION_STATE_INVALID"
            ) from error

        self._authority = authority
        self._descriptor = descriptor
        self._backend = backend
        self._authentication_state = authentication_state
        self._requester_identity = requester_identity.strip()

    @classmethod
    def resolve(
        cls,
        authority: PhysicalWebChatResourceAuthority,
        registry: WebPhysicalIdentityRegistry,
        backend: WebQueueManager,
        *,
        binding_id: str,
        expected_provider: str | None = None,
        expected_logical_actor: str | None = None,
        requester_identity: str = "playwright-worker",
    ) -> "PlaywrightPhysicalResourceAdapter":
        """Resolve Playwright identity from the shared registry only."""
        if not isinstance(
            registry,
            WebPhysicalIdentityRegistry,
        ):
            raise TypeError(
                "registry must be WebPhysicalIdentityRegistry"
            )

        identity = registry.resolve_binding(
            binding_id,
            expected_provider=expected_provider,
            expected_logical_actor=expected_logical_actor,
        )
        return cls.from_identity(
            authority,
            identity,
            backend,
            requester_identity=requester_identity,
        )

    @classmethod
    def from_identity(
        cls,
        authority: PhysicalWebChatResourceAuthority,
        identity: WebPhysicalIdentity,
        backend: WebQueueManager,
        *,
        requester_identity: str = "playwright-worker",
    ) -> "PlaywrightPhysicalResourceAdapter":
        """Build directly from a validated shared identity."""
        if not isinstance(
            identity,
            WebPhysicalIdentity,
        ):
            raise TypeError("identity must be WebPhysicalIdentity")
        return cls(
            authority,
            identity.descriptor,
            backend,
            authentication_state=identity.authentication_state,
            requester_identity=requester_identity,
        )

    @property
    def descriptor(self) -> PhysicalResourceDescriptor:
        return self._descriptor

    @property
    def authority(self) -> PhysicalWebChatResourceAuthority:
        return self._authority

    @property
    def backend(self) -> WebQueueManager:
        return self._backend

    @property
    def authentication_state(self) -> AuthenticationState:
        return self._authentication_state

    async def initialize_runtime(self) -> None:
        """Start Playwright only after authentication is verified."""
        self._require_verified_authentication()
        await self._backend.init_browser_pool()

    def resolve_resource(self) -> PhysicalResourceDescriptor:
        return self._descriptor

    def validate_identity(
        self,
        descriptor: PhysicalResourceDescriptor,
    ) -> bool:
        return descriptor == self._descriptor

    def validate_page_surface(self, waitress_id: str) -> bool:
        page = self._get_page(waitress_id)
        if page is None:
            return False
        try:
            if page.is_closed():
                return False
            normalized = canonicalize_interaction_surface(
                page.url,
            )
        except Exception:
            return False
        return normalized == self._descriptor.canonical_interaction_surface

    def claim_resource(self) -> PhysicalResourceClaim:
        """Claim only when provider authentication is explicitly verified."""
        self._require_verified_authentication()
        return self._authority.claim(
            self._descriptor.physical_resource_id,
            self._requester_identity,
        )

    def begin_execution(
        self,
        claim: PhysicalResourceClaim,
        *,
        ticket_id: str,
        operation_id: str,
        waitress_id: str,
    ) -> PlaywrightPhysicalExecution:
        if claim.physical_resource_id != self._descriptor.physical_resource_id:
            raise PlaywrightPhysicalResourceIdentityError(
                "PLAYWRIGHT_CLAIM_RESOURCE_MISMATCH"
            )
        if not ticket_id.strip():
            raise PlaywrightPhysicalResourceError(
                "TICKET_ID_REQUIRED"
            )
        if not operation_id.strip():
            raise PlaywrightPhysicalResourceError(
                "OPERATION_ID_REQUIRED"
            )
        if not waitress_id.strip():
            raise PlaywrightPhysicalResourceError(
                "WAITRESS_ID_REQUIRED"
            )

        if not self.validate_identity(self._descriptor):
            raise PlaywrightPhysicalResourceIdentityError(
                "PHYSICAL_IDENTITY_CHANGED"
            )
        if not self.validate_page_surface(waitress_id):
            self._authority.quarantine(
                claim,
                "PLAYWRIGHT_PAGE_SURFACE_MISMATCH",
                evidence="begin_execution surface validation failed",
            )
            raise PlaywrightPhysicalResourceIdentityError(
                "PLAYWRIGHT_PAGE_SURFACE_MISMATCH"
            )

        self._authority.begin_execution(
            claim,
            backend=self.BACKEND,
            waitress_id=waitress_id,
            operation_id=operation_id,
        )
        return PlaywrightPhysicalExecution(
            physical_resource_id=claim.physical_resource_id,
            claim_id=claim.claim_id,
            execution_generation=claim.execution_generation,
            ticket_id=ticket_id,
            operation_id=operation_id,
            waitress_id=waitress_id,
        )

    def validate_execution(
        self,
        execution: PlaywrightPhysicalExecution,
    ) -> bool:
        if not isinstance(
            execution,
            PlaywrightPhysicalExecution,
        ):
            return False
        if (
            execution.physical_resource_id
            != self._descriptor.physical_resource_id
        ):
            return False
        return self._authority.validate_execution(
            execution.physical_resource_id,
            execution.claim_id,
            execution.execution_generation,
            operation_id=execution.operation_id,
        )

    def validate_callback(
        self,
        execution: PlaywrightPhysicalExecution,
        *,
        ticket_id: str,
        waitress_id: str,
    ) -> bool:
        if ticket_id != execution.ticket_id:
            return False
        if waitress_id != execution.waitress_id:
            return False
        return self.validate_execution(execution)

    async def send(
        self,
        execution: PlaywrightPhysicalExecution,
        prompt: str,
    ) -> None:
        """Perform one physical send behind Authority fencing."""
        self._require_verified_authentication()
        self._require_current_execution(execution)

        if not prompt.strip():
            raise PlaywrightPhysicalResourceError("PROMPT_REQUIRED")

        page = self._get_page(execution.waitress_id)
        if page is None or page.is_closed():
            self._quarantine_after_runtime_failure(
                execution,
                "PLAYWRIGHT_PAGE_CLOSED",
            )
            raise PlaywrightPhysicalResourceExecutionError(
                "PLAYWRIGHT_PAGE_CLOSED"
            )

        if not self.validate_page_surface(execution.waitress_id):
            self._quarantine_after_runtime_failure(
                execution,
                "PLAYWRIGHT_PAGE_SURFACE_MISMATCH",
            )
            raise PlaywrightPhysicalResourceIdentityError(
                "PLAYWRIGHT_PAGE_SURFACE_MISMATCH"
            )

        try:
            textarea = await self._backend.get_active_locator(
                page,
                "prompt_textarea",
            )
            await textarea.fill(prompt.strip())

            send_button = await self._backend.get_active_locator(
                page,
                "send_button",
            )
            await send_button.click()
        except Exception as error:
            self._quarantine_after_runtime_failure(
                execution,
                f"PLAYWRIGHT_SEND_FAILURE:{type(error).__name__}",
            )
            raise

    async def read_response(
        self,
        execution: PlaywrightPhysicalExecution,
    ) -> str:
        """Read a response only while the fencing tuple remains current."""
        self._require_current_execution(execution)

        page = self._get_page(execution.waitress_id)
        if page is None or page.is_closed():
            self._quarantine_after_runtime_failure(
                execution,
                "PLAYWRIGHT_PAGE_CLOSED",
            )
            raise PlaywrightPhysicalResourceExecutionError(
                "PLAYWRIGHT_PAGE_CLOSED"
            )

        if not self.validate_page_surface(execution.waitress_id):
            self._quarantine_after_runtime_failure(
                execution,
                "PLAYWRIGHT_PAGE_SURFACE_MISMATCH",
            )
            raise PlaywrightPhysicalResourceIdentityError(
                "PLAYWRIGHT_PAGE_SURFACE_MISMATCH"
            )

        try:
            locator = await self._backend.get_active_locator(
                page,
                "response_bubble",
            )
            response_text = (
                await locator.inner_text()
            ).strip()
        except Exception:
            self._quarantine_after_runtime_failure(
                execution,
                "PLAYWRIGHT_RESPONSE_READ_FAILURE",
            )
            raise

        self._require_current_execution(execution)
        return response_text

    def request_cancel(
        self,
        execution: PlaywrightPhysicalExecution,
    ) -> PhysicalResourceSnapshot:
        claim = self._claim_for_execution(execution)
        return self._authority.request_cancel(claim)

    def confirm_termination(
        self,
        execution: PlaywrightPhysicalExecution,
        *,
        evidence: str,
    ) -> PhysicalResourceSnapshot:
        if not evidence.strip():
            raise PlaywrightPhysicalResourceError(
                "TERMINATION_EVIDENCE_REQUIRED"
            )
        claim = self._claim_for_execution(execution)
        return self._authority.release(claim)

    def release_resource(
        self,
        execution: PlaywrightPhysicalExecution,
        *,
        evidence: str,
    ) -> PhysicalResourceSnapshot:
        return self.confirm_termination(
            execution,
            evidence=evidence,
        )

    def quarantine_resource(
        self,
        execution: PlaywrightPhysicalExecution,
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

    async def shutdown(
        self,
        execution: PlaywrightPhysicalExecution | None = None,
        *,
        termination_evidence: str | None = None,
    ) -> PhysicalResourceSnapshot | None:
        """Close Playwright and release only with explicit evidence."""
        close_error: Exception | None = None
        try:
            await self._backend.close_browser_pool()
        except Exception as error:
            close_error = error

        if execution is None:
            if close_error is not None:
                raise close_error
            return None

        if termination_evidence and close_error is None:
            return self.confirm_termination(
                execution,
                evidence=termination_evidence,
            )

        return self.quarantine_resource(
            execution,
            reason="PLAYWRIGHT_SHUTDOWN_WITHOUT_TERMINATION_EVIDENCE",
            evidence=(
                f"{type(close_error).__name__}:{close_error}"
                if close_error
                else None
            ),
        )

    def snapshot(self) -> PhysicalResourceSnapshot:
        return self._authority.snapshot(
            self._descriptor.physical_resource_id,
        )

    def _require_verified_authentication(self) -> None:
        if (
            self._authentication_state
            is not AuthenticationState.VERIFIED
        ):
            raise PlaywrightPhysicalResourceIdentityError(
                "PHYSICAL_EXECUTION_REQUIRES_VERIFIED_AUTHENTICATION:"
                f"{self._authentication_state.value}"
            )

    def _require_current_execution(
        self,
        execution: PlaywrightPhysicalExecution,
    ) -> None:
        if not self.validate_execution(execution):
            raise PlaywrightPhysicalResourceExecutionError(
                "STALE_OR_INVALID_PLAYWRIGHT_EXECUTION"
            )

    def _get_page(self, waitress_id: str):
        try:
            return self._backend.pages[waitress_id]
        except (KeyError, TypeError):
            return None

    def _claim_for_execution(
        self,
        execution: PlaywrightPhysicalExecution,
    ) -> PhysicalResourceClaim:
        if (
            execution.physical_resource_id
            != self._descriptor.physical_resource_id
        ):
            raise PlaywrightPhysicalResourceIdentityError(
                "PLAYWRIGHT_EXECUTION_RESOURCE_MISMATCH"
            )
        return PhysicalResourceClaim(
            physical_resource_id=execution.physical_resource_id,
            claim_id=execution.claim_id,
            owner=self._requester_identity,
            execution_generation=execution.execution_generation,
        )

    def _quarantine_after_runtime_failure(
        self,
        execution: PlaywrightPhysicalExecution,
        reason: str,
    ) -> None:
        try:
            self.quarantine_resource(
                execution,
                reason=reason,
            )
        except Exception:
            return


__all__ = [
    "PlaywrightPhysicalExecution",
    "PlaywrightPhysicalResourceAdapter",
    "PlaywrightPhysicalResourceError",
    "PlaywrightPhysicalResourceExecutionError",
    "PlaywrightPhysicalResourceIdentityError",
]
