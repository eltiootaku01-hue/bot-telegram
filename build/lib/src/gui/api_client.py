from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CommandCenterApiError(RuntimeError):
    pass


class CommandCenterApiClient:
    """Small synchronous HTTP client intended to run only inside a worker thread."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 2.0) -> None:
        self.base_url = (base_url or os.getenv("COMMAND_CENTER_API_URL", "http://127.0.0.1:8770")).rstrip("/")
        self.token = token if token is not None else os.getenv("COMMAND_CENTER_API_TOKEN", os.getenv("VAULT_API_TOKEN", ""))
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[dict, float]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        started = time.perf_counter()
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                elapsed = (time.perf_counter() - started) * 1000
                decoded = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(decoded, dict):
                    raise CommandCenterApiError("API response must be a JSON object")
                return decoded, elapsed
        except HTTPError as exc:
            raise CommandCenterApiError(f"HTTP {exc.code} from CommandCenterService") from exc
        except URLError as exc:
            raise CommandCenterApiError(f"CommandCenterService unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise CommandCenterApiError("CommandCenterService request timed out") from exc
        except json.JSONDecodeError as exc:
            raise CommandCenterApiError("CommandCenterService returned invalid JSON") from exc

    def state(self) -> tuple[dict, float]:
        return self._request("GET", "/api/v1/state")

    def command(self, action: str, identity: str, payload: dict | None = None) -> tuple[dict, float]:
        data = {"identity": identity, **(payload or {})}
        return self._request("POST", f"/api/v1/control/{action}", data)
