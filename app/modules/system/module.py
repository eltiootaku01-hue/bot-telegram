from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.core.module import BotModule


class SystemModule(BotModule):
    name = "system"

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.ping, F.text.casefold() == "ping")

    async def start(self, message: Message) -> None:
        await message.answer("Bot online. El núcleo modular ya está funcionando.")

    async def ping(self, message: Message) -> None:
        await message.answer("pong")
