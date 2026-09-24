# -*- coding: utf-8 -*-
"""Contratos mínimos entre BOT-IA y los providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


class FailureClass(str, Enum):
    """Categoría estable de una falla para salud, fallback y telemetría."""

    NONE = "none"
    QUOTA = "quota"
    AUTHENTICATION = "authentication"
    INPUT = "input"
    TEMPORARY = "temporary"
    PROTOCOL = "protocol"
    PROVIDER = "provider"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class ProviderHealth(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTH_FAILED = "auth_failed"
    TEMPORARILY_DISABLED = "temporarily_disabled"


@dataclass(frozen=True, slots=True)
class ProviderAccount:
    provider_id: str
    account_id: str
    secret_env: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderModel:
    provider_id: str
    model: str


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    provider: str
    model: str
    input_text: str
    max_output_tokens: int
    timeout_seconds: float
    request_id: str
    escalation_reason: str
    account_id: str | None = None
    total_budget_seconds: float = 15.0
    started_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if not all(
            (
                self.provider,
                self.model,
                self.input_text,
                self.request_id,
                self.escalation_reason,
            )
        ):
            raise ValueError(
                "provider, model, input_text, "
                "request_id and escalation_reason "
                "are required"
            )

        if self.max_output_tokens < 1:
            raise ValueError(
                "output limit must be positive"
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout must be positive"
            )

        if self.total_budget_seconds <= 0:
            raise ValueError(
                "total budget must be positive"
            )

        if self.started_at < 0:
            raise ValueError(
                "request start time must be non-negative"
            )

    def remaining_budget(self) -> float:
        return max(
            0.0,
            self.total_budget_seconds - (time.monotonic() - self.started_at),
        )


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    provider: str
    model: str
    status: ProviderStatus
    output_text: str | None
    usage: ProviderUsage
    latency_ms: int
    request_id: str
    error_type: str | None = None
    fallback_used: bool = False
    failure_class: FailureClass = FailureClass.NONE
    account_id: str | None = None
    health: ProviderHealth = ProviderHealth.ACTIVE
    fallback_from: str | None = None
