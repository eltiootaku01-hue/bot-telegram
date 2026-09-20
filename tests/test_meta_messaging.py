import pytest

from app.integrations.meta.messaging import MetaMessagingClient, MetaMessagingError


class RecordingMetaClient(MetaMessagingClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = []

    async def _post(self, *, provider, url, token, payload):
        self.calls.append((provider, url, token, payload))
        return type("Result", (), {"provider": provider, "message_id": "wamid-or-mid", "raw": {}})()


@pytest.mark.asyncio
async def test_whatsapp_text_uses_phone_number_messages_endpoint() -> None:
    client = RecordingMetaClient(
        graph_api_version="v26.0",
        whatsapp_access_token="secret",
        whatsapp_phone_number_id="123456",
    )

    result = await client.send_whatsapp_text("+54 9 11 1234-5678", "Hola desde Cari.")

    provider, url, token, payload = client.calls[0]
    assert result.provider == "whatsapp"
    assert provider == "whatsapp"
    assert url == "https://graph.facebook.com/v26.0/123456/messages"
    assert token == "secret"
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "5491112345678"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hola desde Cari."


@pytest.mark.asyncio
async def test_whatsapp_image_supports_caption() -> None:
    client = RecordingMetaClient(
        whatsapp_access_token="secret",
        whatsapp_phone_number_id="123456",
    )

    await client.send_whatsapp_image(
        "5491112345678",
        "https://example.test/image.jpg",
        caption="Una imagen.",
    )

    payload = client.calls[0][3]
    assert payload["type"] == "image"
    assert payload["image"] == {
        "link": "https://example.test/image.jpg",
        "caption": "Una imagen.",
    }


@pytest.mark.asyncio
async def test_messenger_text_uses_page_messages_endpoint() -> None:
    client = RecordingMetaClient(
        messenger_page_access_token="page-secret",
        messenger_page_id="987654",
    )

    result = await client.send_messenger_text("psid-123", "Hola.")

    provider, url, token, payload = client.calls[0]
    assert result.provider == "messenger"
    assert provider == "messenger"
    assert url == "https://graph.facebook.com/v26.0/987654/messages"
    assert token == "page-secret"
    assert payload["recipient"]["id"] == "psid-123"
    assert payload["message"]["text"] == "Hola."


@pytest.mark.asyncio
async def test_messenger_image_uses_image_attachment() -> None:
    client = RecordingMetaClient(
        messenger_page_access_token="page-secret",
        messenger_page_id="987654",
    )

    await client.send_messenger_image("psid-123", "https://example.test/image.jpg")

    payload = client.calls[0][3]
    assert payload["message"]["attachment"]["type"] == "image"
    assert payload["message"]["attachment"]["payload"]["url"] == "https://example.test/image.jpg"


@pytest.mark.asyncio
async def test_unconfigured_meta_provider_fails_closed() -> None:
    client = MetaMessagingClient()

    with pytest.raises(MetaMessagingError):
        await client.send_whatsapp_text("5491112345678", "hola")

    with pytest.raises(MetaMessagingError):
        await client.send_messenger_text("psid-123", "hola")


def test_graph_api_version_must_be_explicitly_versioned() -> None:
    with pytest.raises(ValueError):
        MetaMessagingClient(graph_api_version="26.0")
