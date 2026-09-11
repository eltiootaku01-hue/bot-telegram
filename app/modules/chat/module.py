from aiogram import F
from aiogram.types import Message

from app.core.module import BotModule


class ChatModule(BotModule):
    """Conversational/community surface. AI is intentionally not called here yet."""

    name = "chat"

    def setup(self) -> None:
        self.router.message.register(self.about, F.text.casefold() == "bot")

    async def about(self, message: Message) -> None:
        await message.answer(
            "💬 Estoy en modo comunidad. Podés hablar conmigo normalmente. "
            "La memoria, personalidad y el router de IA se conectarán en su propia capa."
        )
