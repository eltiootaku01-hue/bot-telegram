from aiogram import Bot, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from app.core.identity import BotIdentity, get_profile
from app.core.module import BotModule
from app.ui.game_keyboards import game_hub_keyboard


class SystemModule(BotModule):
    """Small Telegram surface shared by all identities, with identity-aware copy."""

    name = "system"

    def __init__(self, identity: BotIdentity) -> None:
        self.identity = identity
        self.profile = get_profile(identity)
        super().__init__()

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.ping, F.text.casefold() == "ping")
        if self.identity is BotIdentity.SUNNA:
            self.router.callback_query.register(self.game_hub, F.data == "game:hub")
        self.router.my_chat_member.register(self.bot_added)

    async def start(self, message: Message) -> None:
        text = (
            f"👋 <b>{self.profile.display_name}</b> está despierta.\n\n"
            f"{self.profile.role}."
        )
        if self.identity is BotIdentity.SUNNA:
            text += "\n\n🎮 Zona de juego:"
            await message.answer(text, reply_markup=game_hub_keyboard())
            return
        await message.answer(text)

    async def ping(self, message: Message) -> None:
        await message.answer(f"{self.profile.display_name}: pong")

    async def bot_added(self, event: ChatMemberUpdated, bot: Bot) -> None:
        old_status = event.old_chat_member.status
        new_status = event.new_chat_member.status
        joined = new_status in {"member", "administrator"} and old_status in {"left", "kicked"}
        if not joined or event.chat.type not in {"group", "supergroup"}:
            return
        if self.identity is BotIdentity.SUNNA:
            await bot.send_message(
                event.chat.id,
                "🎮 <b>Sunna se unió a la partida.</b>",
                reply_markup=game_hub_keyboard(),
            )
        else:
            await bot.send_message(
                event.chat.id,
                f"👋 <b>{self.profile.display_name}</b> se unió.\n{self.profile.role}.",
            )

    async def game_hub(self, callback: CallbackQuery) -> None:
        await callback.message.edit_text("🎮 <b>Juegos</b>", reply_markup=game_hub_keyboard())
        await callback.answer()
