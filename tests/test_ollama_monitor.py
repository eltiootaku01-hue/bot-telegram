from __future__ import annotations

from app.services.ollama_monitor import OllamaMonitor


def test_ollama_monitor_reports_online_and_models(monkeypatch) -> None:
    responses = {
        "/api/version": {"version": "0.12.0"},
        "/api/tags": {"models": [{"name": "llama3.2:1b"}, {"name": "other:latest"}]},
        "/api/ps": {"models": [{"name": "llama3.2:1b"}]},
    }

    monkeypatch.setattr(OllamaMonitor, "_get", lambda self, path: responses[path])

    status = OllamaMonitor().snapshot()

    assert status.online is True
    assert status.version == "0.12.0"
    assert status.models == ("llama3.2:1b", "other:latest")
    assert status.running_models == ("llama3.2:1b",)
    assert status.error is None


def test_ollama_monitor_returns_diagnostic_without_raising(monkeypatch) -> None:
    def fail(self, path):
        raise OSError("connection refused")

    monkeypatch.setattr(OllamaMonitor, "_get", fail)

    status = OllamaMonitor().snapshot()

    assert status.online is False
    assert status.error == "connection refused"
