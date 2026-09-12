from __future__ import annotations

from dataclasses import dataclass

import app.services.runtime_monitor as runtime_module
from app.services.ollama_monitor import OllamaStatus
from app.services.runtime_monitor import RuntimeMonitor
from app.services.system_monitor import SystemSnapshot


@dataclass
class FakeOllama:
    def snapshot(self) -> OllamaStatus:
        return OllamaStatus(True, "0.12.3", ("llama3.2:1b",), ("llama3.2:1b",))


def test_runtime_monitor_combines_local_diagnostics(monkeypatch) -> None:
    expected = SystemSnapshot(12.5, 44.0, 31.0)
    monkeypatch.setattr(runtime_module, "snapshot", lambda path: expected)
    monitor = RuntimeMonitor()
    monitor.ollama = FakeOllama()

    result = monitor.snapshot(".")

    assert result.system == expected
    assert result.ollama.online is True
    assert result.ollama.models == ("llama3.2:1b",)
