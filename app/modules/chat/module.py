from aiogram import F
from aiogram.types import Message

from app.characters.models import CharacterIntent
from app.characters.router import CharacterIntentRouter
from app.core.identity import BotIdentity
from app.core.module import BotModule


class ChatModule(BotModule):
    """Deterministic community conversation surface for Cari."""

    name = "chat"

    def __init__(self, identity: BotIdentity = BotIdentity.CARI) -> None:
        super().__init__()
        self.identity = identity
        self.characters = CharacterIntentRouter()

    def setup(self) -> None:
        self.router.message.register(
            self.handle_text,
            F.text.func(self._should_handle_text),
        )

    def _should_handle_text(self, text: str) -> bool:
        return bool(text and (text.casefold().strip() == "bot" or self.characters.classify(text)))

    async def handle_text(self, message: Message) -> None:
        if message.from_user is None or not message.text:
            return
        text = message.text.strip()
        intent = self.characters.classify(text)
        if text.casefold() == "bot":
            intent = CharacterIntent.HELP
        if intent is None:
            return
        response = self.characters.director.choose(
            self.identity,
            intent,
            roll=(message.from_user.id + message.chat.id) % 17,
        )
        if response is None:
            return
        await message.answer(response.scene.text)
        if response.follow_up is not None:
            await message.answer(response.follow_up.text)
