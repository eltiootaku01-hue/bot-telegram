from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True, slots=True)
class ProviderMetrics:
    requests: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_seconds: float = 0.0
    generated_tokens: int = 0

    @property
    def average_latency_seconds(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_latency_seconds / self.successes


@dataclass(frozen=True, slots=True)
class AIMetricsSnapshot:
    providers: tuple[tuple[str, ProviderMetrics], ...]
    last_provider: str | None = None
    last_fallback: str | None = None

    def provider(self, name: str) -> ProviderMetrics:
        for provider, metrics in self.providers:
            if provider == name:
                return metrics
        return ProviderMetrics()


class AIMetrics:
    """Thread-safe in-memory telemetry for AI routing and provider health."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._providers: dict[str, ProviderMetrics] = {}
        self._last_provider: str | None = None
        self._last_fallback: str | None = None

    def begin(self, provider: str) -> float:
        with self._lock:
            current = self._providers.get(provider, ProviderMetrics())
            self._providers[provider] = ProviderMetrics(
                requests=current.requests + 1,
                successes=current.successes,
                failures=current.failures,
                total_latency_seconds=current.total_latency_seconds,
                generated_tokens=current.generated_tokens,
            )
        return monotonic()

    def success(self, provider: str, started_at: float, generated_tokens: int = 0) -> None:
        latency = max(0.0, monotonic() - started_at)
        with self._lock:
            current = self._providers.get(provider, ProviderMetrics())
            self._providers[provider] = ProviderMetrics(
                requests=current.requests,
                successes=current.successes + 1,
                failures=current.failures,
                total_latency_seconds=current.total_latency_seconds + latency,
                generated_tokens=current.generated_tokens + max(0, generated_tokens),
            )
            self._last_provider = provider

    def failure(self, provider: str, started_at: float) -> None:
        latency = max(0.0, monotonic() - started_at)
        with self._lock:
            current = self._providers.get(provider, ProviderMetrics())
            self._providers[provider] = ProviderMetrics(
                requests=current.requests,
                successes=current.successes,
                failures=current.failures + 1,
                total_latency_seconds=current.total_latency_seconds + latency,
                generated_tokens=current.generated_tokens,
            )

    def fallback(self, source: str, target: str, reason: str) -> None:
        with self._lock:
            self._last_fallback = f"{source} → {target}: {reason}"

    def snapshot(self) -> AIMetricsSnapshot:
        with self._lock:
            return AIMetricsSnapshot(
                providers=tuple(sorted(self._providers.items())),
                last_provider=self._last_provider,
                last_fallback=self._last_fallback,
            )
