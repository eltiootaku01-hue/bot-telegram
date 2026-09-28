# -*- coding: utf-8 -*-
"""Contrato puro de autorización de escritura del Supervisor.

Este módulo decide si una autorización contractual es válida. No ejecuta
escrituras, no persiste autorizaciones y no sustituye AuthorityCore.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from .scope import ScopeLock, ScopeOperation
from .task_contract import Task


class AuthorizationSource(str, Enum):
    HUMAN = "HUMAN"
    SYSTEM_POLICY = "SYSTEM_POLICY"
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    AUTOMATION = "AUTOMATION"
    UNKNOWN = "UNKNOWN"


class AuthorizationStatus(str, Enum):
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class AuthorizationCheckResult(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class WriteAuthorization:
    """Registro inmutable de una decisión de autorización contractual."""

    authorization_id: str
    task_id: str
    scope_id: str
    requester: str
    authority: str
    source: AuthorizationSource
    operation: ScopeOperation
    target: str
    status: AuthorizationStatus
    created_at: datetime
    expires_at: datetime | None = None
    reason: str = ""
    evidence_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.authorization_id, "authorization_id"),
            (self.task_id, "task_id"),
            (self.scope_id, "scope_id"),
            (self.requester, "requester"),
            (self.authority, "authority"),
            (self.target, "target"),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must be non-empty")
        object.__setattr__(self, "source", AuthorizationSource(self.source))
        object.__setattr__(self, "operation", ScopeOperation(self.operation))
        object.__setattr__(self, "status", AuthorizationStatus(self.status))
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at <= self.created_at:
                raise ValueError("expires_at must be after created_at")
        if self.source is AuthorizationSource.UNKNOWN:
            raise ValueError("UNKNOWN cannot be an authorization source")

    @classmethod
    def request(
        cls,
        *,
        authorization_id: str,
        task_id: str,
        scope_id: str,
        requester: str,
        authority: str,
        source: AuthorizationSource,
        operation: ScopeOperation,
        target: str,
        created_at: datetime,
        expires_at: datetime | None = None,
        reason: str = "",
        evidence_ids: tuple[str, ...] = (),
        claim_ids: tuple[str, ...] = (),
    ) -> "WriteAuthorization":
        return cls(
            authorization_id=authorization_id,
            task_id=task_id,
            scope_id=scope_id,
            requester=requester,
            authority=authority,
            source=source,
            operation=operation,
            target=target,
            status=AuthorizationStatus.REQUESTED,
            created_at=created_at,
            expires_at=expires_at,
            reason=reason,
            evidence_ids=tuple(evidence_ids),
            claim_ids=tuple(claim_ids),
        )

    def revoked(self, *, reason: str) -> "WriteAuthorization":
        if not reason.strip():
            raise ValueError("revocation reason must be non-empty")
        return replace(self, status=AuthorizationStatus.REVOKED, reason=reason)


AuthorityValidator = Callable[[WriteAuthorization], bool]


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    result: AuthorizationCheckResult
    reason: str


def check_authorization(
    authorization: WriteAuthorization | None,
    task: Task | None,
    scope: ScopeLock | None,
    *,
    current_time: datetime | None = None,
    authority_validator: AuthorityValidator | None = None,
    supervisor_identity: str | None = None,
) -> AuthorizationDecision:
    """Valida autorización sin mutar estado ni ejecutar ninguna operación."""

    if authorization is None or task is None or scope is None:
        return AuthorizationDecision(
            AuthorizationCheckResult.DENIED,
            "missing authorization, task, or scope",
        )

    now = current_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return AuthorizationDecision(
            AuthorizationCheckResult.INVALID,
            "current_time must be timezone-aware",
        )
    now = now.astimezone(timezone.utc)

    if authorization.status is AuthorizationStatus.REVOKED:
        return AuthorizationDecision(AuthorizationCheckResult.REVOKED, "authorization is revoked")
    if authorization.status is AuthorizationStatus.DENIED:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "authorization is denied")
    if authorization.status is AuthorizationStatus.REQUESTED:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "authorization has not been granted")
    if authorization.status is AuthorizationStatus.EXPIRED:
        return AuthorizationDecision(AuthorizationCheckResult.EXPIRED, "authorization is expired")

    if authorization.task_id != task.task_id:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "task identity mismatch")
    if authorization.scope_id != scope.scope_id:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "scope identity mismatch")
    if task.scope_id != authorization.scope_id:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "task is not bound to the authorization scope")
    if authorization.requester != task.requester:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "requester mismatch")

    if supervisor_identity and (
        authorization.requester == supervisor_identity
        and authorization.authority == supervisor_identity
    ):
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "Supervisor cannot self-authorize")

    if not authorization.authority.strip():
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "authority is missing")
    if authorization.source is AuthorizationSource.UNKNOWN:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "authorization source is unknown")
    if authority_validator is None:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "independent authority validation is missing")
    try:
        independently_trusted = bool(authority_validator(authorization))
    except Exception:
        independently_trusted = False
    if not independently_trusted:
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "authority was not independently validated")

    if scope.current_status().value != "ACTIVE":
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "scope is not active")
    if not scope.authorize(authorization.operation, authorization.target):
        return AuthorizationDecision(AuthorizationCheckResult.DENIED, "operation or target exceeds ScopeLock")

    if authorization.expires_at is not None and now >= authorization.expires_at.astimezone(timezone.utc):
        return AuthorizationDecision(AuthorizationCheckResult.EXPIRED, "authorization has expired")

    return AuthorizationDecision(
        AuthorizationCheckResult.AUTHORIZED,
        "authorization is valid within task and ScopeLock",
    )


__all__ = [
    "AuthorizationCheckResult",
    "AuthorizationDecision",
    "AuthorizationSource",
    "AuthorizationStatus",
    "AuthorityValidator",
    "WriteAuthorization",
    "check_authorization",
]
