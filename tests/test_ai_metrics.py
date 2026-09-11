from __future__ import annotations

import time

from app.services.ai_metrics import AIMetrics


def test_ai_metrics_tracks_success_failure_latency_and_fallback() -> None:
    metrics = AIMetrics()

    started = metrics.begin("ollama")
    time.sleep(0.001)
    metrics.success("ollama", started, generated_tokens=12)

    started = metrics.begin("groq")
    metrics.failure("groq", started)
    metrics.fallback("groq", "ollama", "provider unavailable")

    snapshot = metrics.snapshot()

    assert snapshot.provider("ollama").requests == 1
    assert snapshot.provider("ollama").successes == 1
    assert snapshot.provider("ollama").generated_tokens == 12
    assert snapshot.provider("ollama").average_latency_seconds > 0
    assert snapshot.provider("groq").requests == 1
    assert snapshot.provider("groq").failures == 1
    assert snapshot.last_provider == "ollama"
    assert snapshot.last_fallback == "groq → ollama: provider unavailable"


def test_ai_metrics_snapshot_isolated_from_later_mutation() -> None:
    metrics = AIMetrics()
    started = metrics.begin("ollama")
    metrics.success("ollama", started)
    first = metrics.snapshot()

    started = metrics.begin("ollama")
    metrics.success("ollama", started)
    second = metrics.snapshot()

    assert first.provider("ollama").requests == 1
    assert second.provider("ollama").requests == 2
