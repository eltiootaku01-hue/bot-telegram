import pytest

from app.brain.chat import BrainChatModule
from app.core.config import Settings
from app.core.identity import BotIdentity


class FakeChat:
    type = "private"


class FakeMessage:
    chat = FakeChat()
    reply_to_message = None
    text = "hola"

    def __init__(self) -> None:
        self.answer_calls: list[str] = []

    async def answer(self, text: str) -> None:
        self.answer_calls.append(text)


class ExplodingBrain:
    async def generate(self, request):
        raise AssertionError("AI backend must not be called when AI is disabled")


@pytest.mark.asyncio
async def test_brain_chat_is_noop_when_ai_is_disabled() -> None:
    module = BrainChatModule(BotIdentity.CARI, Settings(ai_enabled=False))
    module.brain = ExplodingBrain()  # type: ignore[assignment]
    message = FakeMessage()

    await module.chat(message)  # type: ignore[arg-type]

    assert message.answer_calls == []


def test_brain_chat_uses_identity_override_when_enabled() -> None:
    settings = Settings(ai_enabled=False, ai_enabled_cari=True)
    module = BrainChatModule(BotIdentity.CARI, settings)
    assert settings.ai_for(BotIdentity.CARI) is True
    assert module.settings is settings
