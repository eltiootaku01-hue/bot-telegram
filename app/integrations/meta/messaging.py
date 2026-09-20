from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


class MetaMessagingError(RuntimeError):
    """Raised when Meta rejects or cannot complete an outbound message."""


@dataclass(frozen=True, slots=True)
class MetaSendResult:
    provider: str
    message_id: str | None
    raw: dict[str, Any]


class MetaMessagingClient:
    """Small outbound-only adapter for WhatsApp Cloud API and Messenger Send API.

    The Telegram bot remains the primary runtime. This client is intentionally
    isolated so external messaging can be enabled without coupling Meta APIs to
    character or game logic.
    """

    def __init__(
        self,
        *,
        graph_api_version: str = "v26.0",
        whatsapp_access_token: str = "",
        whatsapp_phone_number_id: str = "",
        messenger_page_access_token: str = "",
        messenger_page_id: str = "",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.graph_api_version = graph_api_version.strip()
        self.whatsapp_access_token = whatsapp_access_token.strip()
        self.whatsapp_phone_number_id = whatsapp_phone_number_id.strip()
        self.messenger_page_access_token = messenger_page_access_token.strip()
        self.messenger_page_id = messenger_page_id.strip()
        self.timeout_seconds = timeout_seconds

        if not self.graph_api_version.startswith("v"):
            raise ValueError("graph_api_version must look like v26.0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.graph_api_version}"

    def whatsapp_configured(self) -> bool:
        return bool(self.whatsapp_access_token and self.whatsapp_phone_number_id)

    def messenger_configured(self) -> bool:
        return bool(self.messenger_page_access_token and self.messenger_page_id)

    async def send_whatsapp_text(self, recipient: str, text: str) -> MetaSendResult:
        self._require_whatsapp()
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._clean_recipient(recipient),
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        return await self._post(
            provider="whatsapp",
            url=f"{self.base_url}/{self.whatsapp_phone_number_id}/messages",
            token=self.whatsapp_access_token,
            payload=payload,
        )

    async def send_whatsapp_image(
        self,
        recipient: str,
        image_url: str,
        *,
        caption: str | None = None,
    ) -> MetaSendResult:
        self._require_whatsapp()
        image: dict[str, str] = {"link": image_url}
        if caption:
            image["caption"] = caption
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._clean_recipient(recipient),
            "type": "image",
            "image": image,
        }
        return await self._post(
            provider="whatsapp",
            url=f"{self.base_url}/{self.whatsapp_phone_number_id}/messages",
            token=self.whatsapp_access_token,
            payload=payload,
        )

    async def send_messenger_text(self, recipient_psid: str, text: str) -> MetaSendResult:
        self._require_messenger()
        payload = {
            "recipient": {"id": recipient_psid.strip()},
            "messaging_type": "RESPONSE",
            "message": {"text": text},
        }
        return await self._post(
            provider="messenger",
            url=f"{self.base_url}/{self.messenger_page_id}/messages",
            token=self.messenger_page_access_token,
            payload=payload,
        )

    async def send_messenger_image(
        self,
        recipient_psid: str,
        image_url: str,
    ) -> MetaSendResult:
        self._require_messenger()
        payload = {
            "recipient": {"id": recipient_psid.strip()},
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {"url": image_url, "is_reusable": True},
                }
            },
        }
        return await self._post(
            provider="messenger",
            url=f"{self.base_url}/{self.messenger_page_id}/messages",
            token=self.messenger_page_access_token,
            payload=payload,
        )

    async def _post(
        self,
        *,
        provider: str,
        url: str,
        token: str,
        payload: dict[str, Any],
    ) -> MetaSendResult:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    body = await response.json(content_type=None)
                    if response.status >= 400:
                        raise MetaMessagingError(
                            f"Meta {provider} send failed with HTTP {response.status}"
                        )
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise MetaMessagingError(
                f"Meta {provider} send failed due to network/timeout"
            ) from exc

        message_id = None
        if isinstance(body, dict):
            message_id = body.get("messages", [{}])[0].get("id") if body.get("messages") else body.get("message_id")
        return MetaSendResult(provider=provider, message_id=message_id, raw=body if isinstance(body, dict) else {})

    @staticmethod
    def _clean_recipient(recipient: str) -> str:
        value = "".join(char for char in recipient if char.isdigit())
        if len(value) < 6:
            raise ValueError("recipient must contain a valid phone/WhatsApp identifier")
        return value

    def _require_whatsapp(self) -> None:
        if not self.whatsapp_configured():
            raise MetaMessagingError(
                "WhatsApp integration is not configured"
            )

    def _require_messenger(self) -> None:
        if not self.messenger_configured():
            raise MetaMessagingError(
                "Messenger integration is not configured"
            )


__all__ = ["MetaMessagingClient", "MetaMessagingError", "MetaSendResult"]
