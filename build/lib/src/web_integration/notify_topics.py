from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger("WebNotificationClient")


class WebNotificationClient:
    """Synchronous client for the authenticated Command Center webhook."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        resolved_base_url = (
            base_url
            or os.getenv("COMMAND_CENTER_API_URL")
            or "http://127.0.0.1:8770"
        ).rstrip("/")
        token = os.getenv("COMMAND_CENTER_TOKEN")
        if not token:
            raise ValueError(
                "Error de configuración: la variable de entorno "
                "'COMMAND_CENTER_TOKEN' debe estar definida."
            )
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.api_url = f"{resolved_base_url}/api/v1/notifications/webhook"
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def notify(
        self,
        event_type: str,
        title: str,
        url: str,
        author: str = "Anónimo",
    ) -> dict:
        payload = {
            "event_type": event_type,
            "title": title,
            "url": url,
            "author": author,
        }

        response = requests.post(
            self.api_url,
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Command Center returned a non-object JSON response")

        logger.info(
            "Notificación entregada exitosamente al thread_id %s",
            data.get("target_thread_id"),
        )
        return data
