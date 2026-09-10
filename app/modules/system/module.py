from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.core.module import BotModule
from app.ui.game_keyboards import game_hub_keyboard


class SystemModule(BotModule):
    """Small non-game Telegram surface; interactive buttons belong to games."""

    name = "system"

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.ping, F.text.casefold() == "ping")
        self.router.callback_query.register(self.game_hub, F.data == "game:hub")

    async def start(self, message: Message) -> None:
        await message.answer(
            "👋 <b>VBot</b> está despierto.\n\n"
            "💬 Podés hablar conmigo normalmente.\n"
            "🎮 Cuando aparezca una waifu, los botones serán parte del evento.\n\n"
            "Zona de juego:",
            reply_markup=game_hub_keyboard(),
        )

    async def ping(self, message: Message) -> None:
        await message.answer("pong")

    async def game_hub(self, callback: CallbackQuery) -> None:
        await callback.message.edit_text("🎮 <b>Juegos</b>", reply_markup=game_hub_keyboard())
        await callback.answer()
