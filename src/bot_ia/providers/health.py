# -*- coding: utf-8 -*-
"""Estado y salud de cuentas de proveedores."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from datetime import datetime, timezone
import time

from .models import FailureClass, ProviderHealth


@dataclass(slots=True)
class ProviderHealthRecord:
    provider_id: str
    account_id: str
    state: ProviderHealth = ProviderHealth.ACTIVE
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_error: str | None = None
    last_failure_class: FailureClass = FailureClass.NONE
    last_success_at: str | None = None
    last_failure_at: str | None = None
    cooldown_until: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    @property
    def available(self) -> bool:
        with self._lock:
            return time.monotonic() >= self.cooldown_until

    def register_success(self, input_tokens: int | None, output_tokens: int | None, total_tokens: int | None) -> None:
        with self._lock:
            self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.state = ProviderHealth.ACTIVE
        self.last_error = None
        self.last_failure_class = FailureClass.NONE
        self.cooldown_until = 0.0
        self.last_success_at = datetime.now(timezone.utc).isoformat()
        if input_tokens is not None:
            self.total_input_tokens += input_tokens
        if output_tokens is not None:
            self.total_output_tokens += output_tokens
        if total_tokens is not None:
            self.total_tokens += total_tokens

    def register_failure(self, error_type: str, failure_class: FailureClass, cooldown_seconds: float = 0.0) -> None:
        with self._lock:
            self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_error = error_type
        self.last_failure_class = failure_class
        self.last_failure_at = datetime.now(timezone.utc).isoformat()
        self.cooldown_until = max(self.cooldown_until, time.monotonic() + max(0.0, cooldown_seconds))
        if failure_class == FailureClass.QUOTA:
            self.state = ProviderHealth.QUOTA_EXHAUSTED
        elif failure_class == FailureClass.AUTHENTICATION:
            self.state = ProviderHealth.AUTH_FAILED
        elif failure_class == FailureClass.TEMPORARY:
            self.state = ProviderHealth.TEMPORARILY_DISABLED
        else:
            self.state = ProviderHealth.DEGRADED
