from __future__ import annotations

import logging

from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, ChatMemberUpdated, Message

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity, get_profile
from app.core.module import BotModule
from app.db.database import Database
from app.services.world import WorldService
from app.ui.control_keyboards import chie_start_keyboard
from app.ui.help_keyboards import help_keyboard
from app.ui.game_keyboards import game_hub_keyboard

logger = logging.getLogger(__name__)


class SystemModule(BotModule):
    """Small Telegram surface shared by all identities, with identity-aware copy."""

    name = "system"

    def __init__(self, identity: BotIdentity, database: Database | None = None, settings: Settings | None = None) -> None:
        self.identity = identity
        self.profile = get_profile(identity)
        self.database = database
        self.settings = settings or get_settings()
        self.world = WorldService()
        super().__init__()

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.help, Command("ayuda"))
        self.router.callback_query.register(self.help_navigation, F.data.startswith("help:"))
        self.router.message.register(self.ping, Command("ping"))
        self.router.message.register(self.id_command, Command("id"))
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
                BotCommand(command="ayuda", description="Ver qué puede hacer Cari"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
                BotCommand(command="id", description="Mostrar tu ID y el ID del chat"),
                BotCommand(command="cafe", description="Abrir el Café Otaku"),
                BotCommand(command="menu", description="Ver el menú del Café Otaku"),
                BotCommand(command="recomendacion", description="Pedir una recomendación del día"),
                BotCommand(command="momento", description="Ver un momento contextual del Café"),
                BotCommand(command="tio_pendientes", description="Ver solicitudes para Tío Otaku"),
                BotCommand(command="tio_historial", description="Ver el historial del operador"),
                BotCommand(command="tio_responder", description="Enviar una respuesta humana a una solicitud"),
                BotCommand(command="advertir", description="Advertir sobre un mensaje"),
                BotCommand(command="silenciar", description="Silenciar a un integrante"),
                BotCommand(command="desilenciar", description="Retirar un silencio"),
                BotCommand(command="expulsar", description="Expulsar a un integrante"),
            ),
            BotIdentity.SUNNA: (
                BotCommand(command="start", description="Abrir la zona de Sunna"),
                BotCommand(command="ayuda", description="Ver qué puede hacer Sunna"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
                BotCommand(command="id", description="Mostrar tu ID y el ID del chat"),
                BotCommand(command="juego", description="Abrir los juegos"),
                BotCommand(command="gacha", description="Abrir el gacha"),
                BotCommand(command="inventario", description="Ver tu inventario"),
                BotCommand(command="combate", description="Abrir combate"),
                BotCommand(command="misterio", description="Resolver el misterio diario"),
                BotCommand(command="trivia", description="Consultar la trivia"),
                BotCommand(command="puntos", description="Consultar tus puntos"),
                BotCommand(command="ranking", description="Consultar el ranking"),
                BotCommand(command="gacha_pendientes", description="Revisar drops raros pendientes"),
            ),
            BotIdentity.CAMI: (
                BotCommand(command="start", description="Presentación de Cami"),
                BotCommand(command="ayuda", description="Ver qué puede hacer Cami"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
                BotCommand(command="id", description="Mostrar tu ID y el ID del chat"),
                BotCommand(command="catalogo", description="Buscar material publicado"),
                BotCommand(command="anime", description="Buscar fichas locales de anime/manga"),
                BotCommand(command="recuperar_publicaciones", description="Revisar entregas ambiguas"),
                BotCommand(command="cola_media", description="Ver la cola de medios de Cami"),
                BotCommand(command="cola_pedidos", description="Ver la cola de pedidos de Cami"),
            ),
            BotIdentity.CHIE: (
                BotCommand(command="start", description="Abrir el panel de Chie"),
                BotCommand(command="ayuda", description="Ver qué puede hacer Chie"),
                BotCommand(command="ping", description="Comprobar que estoy activa"),
                BotCommand(command="id", description="Mostrar tu ID y el ID del chat"),
                BotCommand(command="configurar", description="Configurar la comunidad"),
                BotCommand(command="comandos", description="Abrir el panel de comandos"),
                BotCommand(command="reglas", description="Ver las reglas de la comunidad"),
                BotCommand(command="mundo", description="Ver métricas de Ciudad Animals"),
                BotCommand(command="revisar_mundo", description="Ver la revisión diaria del mundo"),
                BotCommand(command="proponer_mundo", description="Generar propuestas opcionales con IA"),
                BotCommand(command="salud", description="Revisar la salud del sistema"),
                BotCommand(command="borrar_mi_memoria", description="Borrar tus estadísticas privadas"),
                BotCommand(command="mis_pedidos", description="Ver el estado de tus pedidos"),
            ),
        }[self.identity]
        try:
            await bot.set_my_commands(list(commands))
        except TelegramAPIError:
            logger.exception("Could not publish Telegram command menu identity=%s", self.identity.value)


    async def start(self, message: Message) -> None:
        start_parts = message.text.casefold().strip().split(maxsplit=1) if message.text else []
        if (
            self.identity is BotIdentity.CHIE
            and message.chat.type == "private"
            and len(start_parts) == 2
            and start_parts[0].startswith("/start")
            and start_parts[1] == "miid"
            and message.from_user is not None
        ):
            await message.answer(
                "🆔 <b>Tu ID numérico de Telegram</b>\n\n"
                f"<code>{message.from_user.id}</code>\n\n"
                "Pegá este número en Bot Manager → Maestro / Jefe. "
                "Es el identificador operativo de permisos; no hace falta guardar tu número de teléfono."
            )
            return

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

    async def help(self, message: Message) -> None:
        help_texts = {
            BotIdentity.CARI: (
                "👋 <b>Ayuda de Cari</b>\n\n"
                "☕ <code>/cafe</code> — abre el Café Otaku.\n"
                "🍿 <code>/recomendacion</code> — recomendación diaria.\n"
                "💬 Podés hablarme de forma natural sobre anime, manga o pedir ayuda.\n"
                "🛡️ En grupos, las herramientas de moderación solo funcionan para administradores."
            ),
            BotIdentity.SUNNA: (
                "🎮 <b>Ayuda de Sunna</b>\n\n"
                "🎲 <code>/juego</code> — abre la zona de juegos.\n"
                "🎰 <code>/gacha</code> — abre el gacha.\n"
                "🎒 <code>/inventario</code> — muestra tu colección.\n"
                "⚔️ <code>/combate</code> — abre combate.\n"
                "🧠 <code>/trivia</code> — consulta la trivia.\n"
                "💰 <code>/puntos</code> y <code>/ranking</code> — progreso comunitario.\n"
                "🌟 WaifuMon aparece en la comunidad configurada."
            ),
            BotIdentity.CAMI: (
                "📚 <b>Ayuda de Cami</b>\n\n"
                "🗂️ <code>/catalogo</code> — buscar material publicado.\n"
                "📖 <code>/anime</code> — buscar fichas locales de anime/manga.\n"
                "🔎 <code>/anime_ficha</code> — abrir una ficha concreta.\n"
                "🔁 <code>/recuperar_publicaciones</code> — revisar entregas ambiguas como administradora.\n"
                "📋 <code>/cola_media</code> y <code>/cola_pedidos</code> — paneles operativos privados.
"
                "ℹ️ El archivo local no completa datos faltantes con IA."
            ),
            BotIdentity.CHIE: (
                "📋 <b>Ayuda de Chie</b>\n\n"
                "⚙️ <code>/configurar</code> — preparar la comunidad y sus temas.\n"
                "📌 <code>/comandos</code> — abrir el panel comunitario.\n"
                "📜 <code>/reglas</code> — consultar las reglas.\n"
                "🌍 <code>/mundo</code> — métricas de Ciudad Animals.\n"
                "🩺 <code>/salud</code> — estado técnico para el administrador.\n"
                "📋 <code>/mis_pedidos</code> — ver el estado de tus pedidos de imágenes.
"
                "💡 <code>/revisar_mundo</code> y <code>/proponer_mundo</code> — revisión/propuestas del mundo."
            ),
        }
        await message.answer(help_texts[self.identity], reply_markup=help_keyboard(self.identity))

    async def help_navigation(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None or not callback.data:
            await callback.answer("Ayuda inválida.", show_alert=True)
            return
        parts = callback.data.split(":")
        if len(parts) != 3 or parts[1] != self.identity.value:
            await callback.answer("Esta ayuda pertenece a otra identidad.", show_alert=True)
            return

        section = parts[2]
        details = {
            BotIdentity.CARI: {
                "cafe": (
                    "☕ <b>Café Otaku</b>\n\n"
                    "Usá <code>/cafe</code> para ver los servicios del café.\n"
                    "También podés usar <code>/menu</code> para repetir el menú."
                ),
                "recommendation": (
                    "🍿 <b>Recomendación</b>\n\n"
                    "<code>/recomendacion</code> entrega una recomendación determinista del día."
                ),
                "conversation": (
                    "💬 <b>Conversación</b>\n\n"
                    "Cari responde de forma authored-only a interacciones reconocidas. "
                    "No necesita un LLM para su comportamiento cotidiano."
                ),
                "moderation": (
                    "🛡️ <b>Moderación</b>\n\n"
                    "Las herramientas de moderación están disponibles para administradores del grupo y respetan la allowlist central."
                ),
            },
            BotIdentity.SUNNA: {
                "games": (
                    "🎮 <b>Juegos</b>\n\n"
                    "Abrí <code>/juego</code> para entrar al panel. Desde ahí tenés gacha, inventario, combate y trivia."
                ),
                "gacha": (
                    "🎰 <b>Gacha</b>\n\n"
                    "Usá <code>/gacha</code> para abrirlo. La tirada se resuelve localmente."
                ),
                "inventory": (
                    "🎒 <b>Inventario</b>\n\n"
                    "<code>/inventario</code> muestra tu colección y las evoluciones disponibles."
                ),
                "points": (
                    "💰 <b>Puntos</b>\n\n"
                    "<code>/puntos</code> consulta tu saldo y <code>/ranking</code> muestra el estado comunitario."
                ),
            },
            BotIdentity.CAMI: {
                "catalog": (
                    "📚 <b>Catálogo</b>\n\n"
                    "<code>/catalogo</code> busca material local. Cami no inventa registros que no existan."
                ),
                "anime": (
                    "📖 <b>Anime y manga</b>\n\n"
                    "<code>/anime</code> busca fichas locales y <code>/anime_ficha</code> abre una ficha concreta."
                ),
                "recovery": (
                    "🔁 <b>Recuperación</b>\n\n"
                    "<code>/recuperar_publicaciones</code> permite revisar entregas ambiguas como administradora."
                ),
                "archive": (
                    "📊 <b>Archivo</b>\n\n"
                    "Cami mantiene catálogo, publicaciones, pedidos y estadísticas sin convertir la IA en autoridad del archivo."
                ),
            },
            BotIdentity.CHIE: {
                "configure": (
                    "⚙️ <b>Configurar</b>\n\n"
                    "<code>/configurar</code> verifica permisos de administradora y prepara los temas de la comunidad."
                ),
                "commands": (
                    "📌 <b>Comandos</b>\n\n"
                    "<code>/comandos</code> abre el panel comunitario con accesos a las áreas principales."
                ),
                "rules": (
                    "📜 <b>Reglas</b>\n\n"
                    "<code>/reglas</code> consulta las reglas locales de la comunidad."
                ),
                "world": (
                    "🌍 <b>Ciudad Animals</b>\n\n"
                    "<code>/mundo</code> muestra métricas agregadas y <code>/revisar_mundo</code> revisa tendencias sin reescribir el canon."
                ),
            },
        }

        text = details.get(self.identity, {}).get(section)
        if text is None:
            await callback.answer("Sección no disponible.", show_alert=True)
            return

        await callback.message.edit_text(
            text,
            reply_markup=help_keyboard(self.identity, section),
        )
        await callback.answer()

    async def id_command(self, message: Message) -> None:
        """Show Telegram numeric IDs needed by Bot Manager setup."""
        user_id = message.from_user.id if message.from_user is not None else "desconocido"
        await message.answer(
            f"🆔 <b>ID de usuario:</b> <code>{user_id}</code>\n"
            f"💬 <b>ID del chat:</b> <code>{message.chat.id}</code>\n\n"
            "Para Bot Manager, usá tu ID como Maestro/Jefe y, si este es el grupo general, "
            "usá el ID del chat como Grupo base."
        )

    async def ping(self, message: Message) -> None:
        await message.answer(f"{self.profile.display_name}: pong")

    async def bot_added(self, event: ChatMemberUpdated, bot: Bot) -> None:
        old_status = event.old_chat_member.status
        new_status = event.new_chat_member.status
        joined = new_status in {"member", "administrator"} and old_status in {"left", "kicked"}
        if not joined or event.chat.type not in {"group", "supergroup"}:
            return
        if not is_authorized_community(self.settings, event.chat.id):
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
