from aiogram.filters import Command
from aiogram.types import Message

from app.core.module import BotModule


class MediaModule(BotModule):
    """Requests, image catalog and publishing order; administration moves to web later."""

    name = "media"

    def setup(self) -> None:
        self.router.message.register(self.request, Command("pedido"))

    async def request(self, message: Message) -> None:
        await message.answer(
            "📥 Pedido recibido. La cola de pedidos e imágenes se conectará a la biblioteca. "
            "La gestión completa quedará en la web privada."
        )
