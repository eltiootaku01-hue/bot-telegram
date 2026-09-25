from __future__ import annotations

from dataclasses import dataclass

from app.services.ollama_monitor import OllamaMonitor, OllamaStatus
from app.services.system_monitor import SystemSnapshot, snapshot


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    system: SystemSnapshot
    ollama: OllamaStatus


class RuntimeMonitor:
    """Cheap read-only runtime diagnostics for the native manager UI.

    Diagnostics never invoke an LLM and never spend cloud API credits.
    """

    def __init__(self, ollama_base_url: str = "http://127.0.0.1:11434") -> None:
        self.ollama = OllamaMonitor(ollama_base_url)

    def snapshot(self, path: str = ".") -> RuntimeSnapshot:
        return RuntimeSnapshot(system=snapshot(path), ollama=self.ollama.snapshot())
