from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class OllamaStatus:
    online: bool
    version: str | None = None
    models: tuple[str, ...] = ()
    running_models: tuple[str, ...] = ()
    error: str | None = None


class OllamaMonitor:
    """Read-only local Ollama diagnostics; never generates text or spends API credits."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 0.8) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def snapshot(self) -> OllamaStatus:
        try:
            version = self._get("/api/version").get("version")
            tags = self._get("/api/tags").get("models", [])
            running = self._get("/api/ps").get("models", [])
            models = tuple(str(item.get("name", "")) for item in tags if item.get("name"))
            running_models = tuple(str(item.get("name", "")) for item in running if item.get("name"))
            return OllamaStatus(True, str(version) if version else None, models, running_models)
        except (OSError, URLError, ValueError, KeyError, TypeError) as exc:
            return OllamaStatus(False, error=str(exc))

    def _get(self, path: str) -> dict:
        request = Request(f"{self.base_url}{path}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Ollama devolvió una respuesta JSON inválida")
        return payload
