from __future__ import annotations

from enum import StrEnum

from app.integrations.meta.messaging import MetaMessagingClient, MetaSendResult


class ContactProvider(StrEnum):
    WHATSAPP = "whatsapp"
    MESSENGER = "messenger"


class MetaContactGateway:
    """Provider-neutral facade for explicit outbound human contact."""

    def __init__(self, client: MetaMessagingClient) -> None:
        self.client = client

    async def send_text(
        self,
        provider: ContactProvider | str,
        recipient: str,
        text: str,
    ) -> MetaSendResult:
        provider_name = ContactProvider(provider)
        if provider_name is ContactProvider.WHATSAPP:
            return await self.client.send_whatsapp_text(recipient, text)
        return await self.client.send_messenger_text(recipient, text)

    async def send_image(
        self,
        provider: ContactProvider | str,
        recipient: str,
        image_url: str,
        *,
        caption: str | None = None,
    ) -> MetaSendResult:
        provider_name = ContactProvider(provider)
        if provider_name is ContactProvider.WHATSAPP:
            return await self.client.send_whatsapp_image(
                recipient,
                image_url,
                caption=caption,
            )
        result = await self.client.send_messenger_image(recipient, image_url)
        if caption:
            await self.client.send_messenger_text(recipient, caption)
        return result


__all__ = ["ContactProvider", "MetaContactGateway"]
