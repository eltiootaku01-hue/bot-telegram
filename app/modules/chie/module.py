from aiogram import Bot, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatMemberAdministrator, Message
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.community_models import SetupSession
from app.db.database import Database
from app.services.forum_topics import ForumTopicService
from app.ui.control_keyboards import command_hub_keyboard, chie_setup_keyboard


REQUIRED_ADMIN_PERMISSIONS = {
    "can_manage_topics": "gestionar temas",
    "can_delete_messages": "eliminar mensajes",
    "can_restrict_members": "restringir miembros",
}


class ChieModule(BotModule):
    """Community coordinator: setup, permissions and a button-first command surface."""

    name = "chie"

    def __init__(self, database: Database) -> None:
        self.database = database
        self.topics = ForumTopicService(database)
        super().__init__()

    def setup(self) -> None:
        self.router.callback_query.register(self.start_setup, F.data == "chie:setup:start")
        self.router.callback_query.register(self.check_setup, F.data == "chie:setup:check")
        self.router.callback_query.register(self.cancel_setup, F.data == "chie:setup:cancel")
        self.router.callback_query.register(self.command_hub, F.data.startswith("chie:hub:"))
        self.router.message.register(self.configure_group, Command("configurar"))
        self.router.message.register(self.command_hub_command, Command("comandos"))

    async def start_setup(self, callback: CallbackQuery) -> None:
        if not callback.message or callback.message.chat.type != "private":
            await callback.answer("Abrime en privado para iniciar la configuración.", show_alert=True)
            return
        await callback.answer()
        await callback.message.answer(
            "😰 O-okay... primero necesito saber <b>qué grupo</b> voy a cuidar.\n\n"
            "1. Agregame como administradora al grupo.\n"
            "2. En ese grupo escribe <code>/configurar</code>.\n"
            "3. Volvé acá y tocá <b>Ya me agregaste de admin</b>.\n\n"
            "No voy a confiar en que me digas que soy admin: voy a comprobar mis permisos directamente.",
            reply_markup=chie_setup_keyboard(),
        )

    async def configure_group(self, message: Message, bot: Bot) -> None:
        if message.chat.type not in {"group", "supergroup"}:
            await message.answer("😰 Ese comando tiene que ejecutarse dentro del grupo que querés configurar.")
            return
        member = await bot.get_chat_member(message.chat.id, bot.id)
        if not isinstance(member, ChatMemberAdministrator):
            await message.answer("😰 Necesito ser administradora del grupo antes de reformarlo.")
            return

        missing = [label for attr, label in REQUIRED_ADMIN_PERMISSIONS.items() if not getattr(member, attr, False)]
        if missing:
            await message.answer("Me faltan estos permisos: " + ", ".join(missing) + ".")
            return

        async with self.database.session() as session:
            existing = await session.scalar(
                select(SetupSession).where(
                    SetupSession.user_id == message.from_user.id,
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                )
            )
            if existing:
                existing.chat_id = message.chat.id
                existing.status = "awaiting_confirmation"
            else:
                session.add(
                    SetupSession(
                        user_id=message.from_user.id,
                        chat_id=message.chat.id,
                        bot_identity=BotIdentity.CHIE.value,
                        status="awaiting_confirmation",
                    )
                )
            await session.commit()

        await message.answer(
            "✅ Permisos comprobados. Ya sé qué grupo configurar.\n\n"
            "Volvé al chat privado conmigo y tocá <b>Ya me agregaste de admin</b>."
        )

    async def check_setup(self, callback: CallbackQuery, bot: Bot) -> None:
        if not callback.from_user or not callback.message:
            return
        async with self.database.session() as session:
            setup = await session.scalar(
                select(SetupSession).where(
                    SetupSession.user_id == callback.from_user.id,
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                    SetupSession.status == "awaiting_confirmation",
                )
            )
            if not setup:
                await callback.answer("Primero ejecutá /configurar dentro del grupo.", show_alert=True)
                return
            chat_id = setup.chat_id

        member = await bot.get_chat_member(chat_id, bot.id)
        missing = [] if isinstance(member, ChatMemberAdministrator) else list(REQUIRED_ADMIN_PERMISSIONS.values())
        if isinstance(member, ChatMemberAdministrator):
            missing = [label for attr, label in REQUIRED_ADMIN_PERMISSIONS.items() if not getattr(member, attr, False)]
        if missing:
            await callback.answer("Todavía me faltan: " + ", ".join(missing), show_alert=True)
            return

        topic_keys = ("noticias", "undiacomohoy", "recomendaciondiaria", "curiosidades", "estrenos", "memes", "material", "anime", "debates", "trivia", "waifumon", "puntos", "pedidos")
        created = 0
        failures: list[str] = []
        for key in topic_keys:
            try:
                before = await self.topics.get_thread_id(chat_id, key)
                await self.topics.ensure_topic(bot, chat_id, key, bot_identity=BotIdentity.CHIE.value)
                created += before is None
            except (RuntimeError, TelegramBadRequest, TelegramForbiddenError) as exc:
                failures.append(f"{key}: {exc}")
                break

        async with self.database.session() as session:
            setup = await session.scalar(
                select(SetupSession).where(
                    SetupSession.user_id == callback.from_user.id,
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                )
            )
            if setup:
                setup.status = "configured" if not failures else "partial"
                await session.commit()

        await callback.answer("Configuración terminada." if not failures else "Configuración parcial.", show_alert=False)
        text = f"🎉 <b>Chie ya está trabajando.</b>\nTemas creados en esta pasada: {created}."
        if failures:
            text += "\n\n⚠️ Me detuve porque Telegram rechazó la creación de temas. Revisá que el grupo sea supergrupo y tenga Foro activado."
        await callback.message.edit_text(text, reply_markup=command_hub_keyboard())

    async def cancel_setup(self, callback: CallbackQuery) -> None:
        if callback.message:
            await callback.message.edit_text("Configuración cancelada. Cuando quieras, tocá /start y volvemos a intentarlo.")
        await callback.answer()

    async def command_hub_command(self, message: Message) -> None:
        await message.answer(
            "🤖 <b>Panel de la comunidad</b>\nElegí qué querés hacer. Los botones llaman funciones concretas; los comandos quedan como acceso alternativo.",
            reply_markup=command_hub_keyboard(),
        )

    async def command_hub(self, callback: CallbackQuery) -> None:
        if not callback.message:
            return
        section = (callback.data or "").rsplit(":", 1)[-1]
        labels = {
            "community": "👋 Comunidad: bienvenida, verificación y moderación.",
            "games": "🎮 Juegos: Sunna gestiona WaifuMon y trivia.",
            "content": "📰 Contenido: noticias, recomendaciones, curiosidades y estrenos.",
            "points": "💰 Puntos: consulta y canjes mediante las funciones autorizadas.",
            "config": "⚙️ Configuración: Chie comprueba permisos y mantiene la estructura.",
        }
        await callback.message.edit_text(labels.get(section, "Panel de la comunidad."), reply_markup=command_hub_keyboard())
        await callback.answer()
