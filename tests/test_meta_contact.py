import pytest

from app.integrations.meta.contact import ContactProvider, MetaContactGateway
from app.integrations.meta.messaging import MetaSendResult


class FakeClient:
    def __init__(self):
        self.calls = []

    async def send_whatsapp_text(self, recipient, text):
        self.calls.append(("whatsapp_text", recipient, text))
        return MetaSendResult("whatsapp", "wa-text", {})

    async def send_messenger_text(self, recipient, text):
        self.calls.append(("messenger_text", recipient, text))
        return MetaSendResult("messenger", "m-text", {})

    async def send_whatsapp_image(self, recipient, image_url, *, caption=None):
        self.calls.append(("whatsapp_image", recipient, image_url, caption))
        return MetaSendResult("whatsapp", "wa-image", {})

    async def send_messenger_image(self, recipient, image_url):
        self.calls.append(("messenger_image", recipient, image_url))
        return MetaSendResult("messenger", "m-image", {})


@pytest.mark.asyncio
async def test_gateway_routes_text_by_provider() -> None:
    client = FakeClient()
    gateway = MetaContactGateway(client)

    whatsapp = await gateway.send_text(ContactProvider.WHATSAPP, "5491112345678", "hola")
    messenger = await gateway.send_text("messenger", "psid", "hola")

    assert whatsapp.message_id == "wa-text"
    assert messenger.message_id == "m-text"
    assert client.calls == [
        ("whatsapp_text", "5491112345678", "hola"),
        ("messenger_text", "psid", "hola"),
    ]


@pytest.mark.asyncio
async def test_gateway_routes_images_by_provider() -> None:
    client = FakeClient()
    gateway = MetaContactGateway(client)

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
async def test_gateway_sends_messenger_image_then_caption() -> None:
    client = FakeClient()
    gateway = MetaContactGateway(client)

    result = await gateway.send_image(
        ContactProvider.MESSENGER,
        "psid",
        "https://example.test/a.jpg",
        caption="Imagen",
    )

    assert result.message_id == "m-image"
    assert client.calls == [
        ("messenger_image", "psid", "https://example.test/a.jpg"),
        ("messenger_text", "psid", "Imagen"),
    ]
