from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.core.module import BotModule


class SystemModule(BotModule):
    """Small non-game Telegram surface; interactive buttons belong to games."""

    name = "system"

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.ping, F.text.casefold() == "ping")

    async def start(self, message: Message) -> None:
        await message.answer(
            "👋 Hola. Soy el bot de la comunidad.\n\n"
            "Podés hablar conmigo normalmente. Los juegos usan botones interactivos; "
            "la administración y gestión se hará desde la web privada.\n\n"
            "Probá /gacha o /combate para entrar al prototipo del juego."
        )

    async def ping(self, message: Message) -> None:
        await message.answer("pong")
