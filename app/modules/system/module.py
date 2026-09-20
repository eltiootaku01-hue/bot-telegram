from __future__ import annotations

import logging

from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, ChatMemberUpdated, Message

from app.core.identity import BotIdentity, get_profile
from app.core.module import BotModule
from app.db.database import Database
from app.services.world import WorldService
from app.ui.control_keyboards import chie_start_keyboard
from app.ui.game_keyboards import game_hub_keyboard

logger = logging.getLogger(__name__)


class SystemModule(BotModule):
    """Small Telegram surface shared by all identities, with identity-aware copy."""

    name = "system"

    def __init__(self, identity: BotIdentity, database: Database | None = None) -> None:
        self.identity = identity
        self.profile = get_profile(identity)
        self.database = database
        self.world = WorldService()
        super().__init__()

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.ping, Command("ping"))
        self.router.message.register(self.ping, F.text.casefold() == "ping")
        if self.identity is BotIdentity.SUNNA:
            self.router.callback_query.register(self.game_hub, F.data == "game:hub")
        self.router.my_chat_member.register(self.bot_added)

    async def on_startup(self, bot: Bot) -> None:
        """Seed shared world state and publish this identity's Telegram menu."""
        if self.database is not None:
            async with self.database.session() as session:
                await self.world.seed_catalog(session)
        commands = {
            BotIdentity.CARI: (
                BotCommand(command="start", description="Presentación de Cari"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
            ),
            BotIdentity.SUNNA: (
                BotCommand(command="start", description="Abrir la zona de Sunna"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
                BotCommand(command="juego", description="Abrir los juegos"),
                BotCommand(command="gacha", description="Abrir el gacha"),
                BotCommand(command="inventario", description="Ver tu inventario"),
                BotCommand(command="combate", description="Abrir combate"),
                BotCommand(command="misterio", description="Resolver el misterio diario"),
                BotCommand(command="trivia", description="Consultar la trivia"),
                BotCommand(command="puntos", description="Consultar tus puntos"),
                BotCommand(command="ranking", description="Consultar el ranking"),
            ),
            BotIdentity.CAMI: (
                BotCommand(command="start", description="Presentación de Cami"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
                BotCommand(command="recuperar_publicaciones", description="Revisar entregas ambiguas"),
            ),
            BotIdentity.CHIE: (
                BotCommand(command="start", description="Abrir el panel de Chie"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
                BotCommand(command="configurar", description="Configurar la comunidad"),
                BotCommand(command="comandos", description="Abrir el panel de comandos"),
                BotCommand(command="reglas", description="Ver las reglas de la comunidad"),
                BotCommand(command="mundo", description="Ver métricas de Ciudad Animals"),
                BotCommand(command="salud", description="Revisar la salud del sistema"),
                BotCommand(command="borrar_mi_memoria", description="Borrar tus estadísticas privadas"),
            ),
        }[self.identity]
        try:
            await bot.set_my_commands(list(commands))
        except TelegramAPIError:
            logger.exception("Could not publish Telegram command menu identity=%s", self.identity.value)


    async def start(self, message: Message) -> None:
        text = (
            f"👋 <b>{self.profile.display_name}</b> está despierta.\n\n"
            f"{self.profile.role}."
        )
        if self.identity is BotIdentity.SUNNA:
            text += "\n\n🎮 Zona de juego:"
            await message.answer(text, reply_markup=game_hub_keyboard())
            return
        if self.identity is BotIdentity.CHIE:
            text += (
                "\n\n😰 Si querés que prepare el grupo, primero necesito que me agregues "
                "como administradora y después comprobaré los permisos."
            )
            await message.answer(text, reply_markup=chie_start_keyboard())
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
