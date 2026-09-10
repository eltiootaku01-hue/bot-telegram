from aiogram import Bot, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from app.core.module import BotModule
from app.ui.game_keyboards import game_hub_keyboard


class SystemModule(BotModule):
    """Small non-game Telegram surface; interactive buttons belong to games."""

    name = "system"

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.ping, F.text.casefold() == "ping")
        self.router.callback_query.register(self.game_hub, F.data == "game:hub")
        self.router.my_chat_member.register(self.bot_added)

    async def start(self, message: Message) -> None:
        await message.answer(
            "👋 <b>VBot</b> está despierto.\n\n"
            "💬 Podés hablar conmigo normalmente.\n"
            "🎮 Los botones interactivos aparecen solo en los juegos.\n\n"
            "Zona de juego:",
            reply_markup=game_hub_keyboard(),
        )

    async def ping(self, message: Message) -> None:
        await message.answer("pong")

    async def bot_added(self, event: ChatMemberUpdated, bot: Bot) -> None:
        old_status = event.old_chat_member.status
        new_status = event.new_chat_member.status
        joined = new_status in {"member", "administrator"} and old_status in {"left", "kicked"}
        if not joined or event.chat.type not in {"group", "supergroup"}:
            return
        await bot.send_message(
            event.chat.id,
            "🎮 <b>VBot se unió a la partida.</b>\n\n"
            "Podés usar estos accesos; el resto de la interfaz aparecerá solo cuando corresponda.",
            reply_markup=game_hub_keyboard(),
        )

    async def game_hub(self, callback: CallbackQuery) -> None:
        await callback.message.edit_text("🎮 <b>Juegos</b>", reply_markup=game_hub_keyboard())
        await callback.answer()
