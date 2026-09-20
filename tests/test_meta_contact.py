import pytest

from app.integrations.meta.contact import ContactProvider, MetaContactGateway
from app.integrations.meta.messaging import MetaSendResult


class FakeClient:
    async def send_whatsapp_text(self, recipient, text):
        return MetaSendResult("whatsapp", "wa-text", {})

    async def send_messenger_text(self, recipient, text):
        return MetaSendResult("messenger", "m-text", {})

    async def send_whatsapp_image(self, recipient, image_url, *, caption=None):
        return MetaSendResult("whatsapp", "wa-image", {})

    async def send_messenger_image(self, recipient, image_url):
        return MetaSendResult("messenger", "m-image", {})


@pytest.mark.asyncio
async def test_gateway_routes_text_by_provider() -> None:
    gateway = MetaContactGateway(FakeClient())

    whatsapp = await gateway.send_text(ContactProvider.WHATSAPP, "5491112345678", "hola")
    messenger = await gateway.send_text("messenger", "psid", "hola")

    assert whatsapp.message_id == "wa-text"
    assert messenger.message_id == "m-text"


@pytest.mark.asyncio
async def test_gateway_routes_images_by_provider() -> None:
    gateway = MetaContactGateway(FakeClient())

    whatsapp = await gateway.send_image(
        "whatsapp",
        "5491112345678",
        "https://example.test/a.jpg",
        caption="A",
    )
    messenger = await gateway.send_image(
        "messenger",
        "psid",
        "https://example.test/a.jpg",
    )

    assert whatsapp.message_id == "wa-image"
    assert messenger.message_id == "m-image"


@pytest.mark.asyncio
async def test_gateway_sends_messenger_caption_as_text_fallback() -> None:
    gateway = MetaContactGateway(FakeClient())

    result = await gateway.send_image(
        ContactProvider.MESSENGER,
        "psid",
        "https://example.test/a.jpg",
        caption="Imagen",
    )

    assert result.message_id == "m-text"
