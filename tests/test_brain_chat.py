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


def test_brain_chat_group_addressing_is_scoped_to_this_identity() -> None:
    module = BrainChatModule(BotIdentity.SUNNA, Settings(ai_enabled=False))

    class Group:
        type = "supergroup"

    class User:
        is_bot = False
        id = 7

    class FakeGroupMessage:
        chat = Group()
        reply_to_message = None
        text = "Cami, necesito revisar esto"
        from_user = User()

    class OtherBotReply:
        from_user = type("BotUser", (), {"is_bot": True, "id": 99})()

    class CurrentBot:
        id = 100

    class ReplyMessage:
        chat = Group()
        reply_to_message = OtherBotReply()
        text = "Sunna, mirá esto"
        from_user = User()
        bot = CurrentBot()

    class OwnReplyMessage:
        chat = Group()
        reply_to_message = type("OwnReply", (), {"from_user": type("BotUser", (), {"is_bot": True, "id": 100})()})()
        text = "mirá esto"
        from_user = User()
        bot = CurrentBot()

    assert module._directly_addressed(FakeGroupMessage()) is False
    assert module._directly_addressed(ReplyMessage()) is False
    assert module._directly_addressed(OwnReplyMessage()) is True


def test_brain_chat_accepts_this_identity_name_with_a_complex_prompt() -> None:
    module = BrainChatModule(BotIdentity.SUNNA, Settings(ai_enabled=False))

    class Group:
        type = "group"

    message = type(
        "FakeMessage",
        (),
        {
            "chat": Group(),
            "reply_to_message": None,
            "text": "Sunna, ¿qué personajes puedo capturar?",
        },
    )()

    assert module._directly_addressed(message) is True
