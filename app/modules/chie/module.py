from __future__ import annotations

import asyncio
import logging
from html import escape

from aiogram import Bot, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatMemberAdministrator, ChatMemberOwner, ChatMemberUpdated, ChatPermissions, Message
from sqlalchemy import select

from app.core.access import is_authorized_community, is_chat_staff
from app.core.config import Settings, get_settings
from app.core.events import EventBus
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.time import world_now
from app.core.workers import DurableWorker
from app.db.community_models import SetupSession
from app.db.models import HumanVerification
from app.db.world_models import WorldProposal, WorldReview
from app.db.database import Database
from app.services.forum_topics import ForumTopicService
from app.services.human_verification import HumanVerificationService, permissions_from_json, permissions_to_json
from app.services.operator_health import OperatorHealthService, format_operator_health
from app.services.world import WorldService
from app.services.world_curator import WorldCuratorService, format_world_review
from app.services.world_curator_ai import WorldCuratorAIService, format_world_proposals
from app.ui.control_keyboards import (
    chie_setup_keyboard,
    chie_human_verification_keyboard,
    command_hub_detail_keyboard,
    command_hub_keyboard,
    world_proposal_keyboard,
)

logger = logging.getLogger(__name__)


REQUIRED_ADMIN_PERMISSIONS = {
    "can_manage_topics": "gestionar temas",
    "can_delete_messages": "eliminar mensajes",
    "can_restrict_members": "restringir miembros",
}

COMMUNITY_RULES = (
    "📜 <b>Reglas de Ciudad Animals</b>\n\n"
    "1. Respeto entre integrantes: nada de acoso, amenazas o ataques personales.\n"
    "2. Nada de spam, flood o contenido diseñado para molestar.\n"
    "3. No compartas datos personales de otras personas sin permiso.\n"
    "4. Usa cada tema del foro para su propósito y evita desviar conversaciones constantemente.\n"
    "5. Los juegos, puntos y pedidos deben usarse de forma honesta; no intentes explotar errores.\n"
    "6. Respeta las indicaciones de los moderadores y de Chie.\n"
    "7. El material ilegal o que infrinja las reglas de Telegram no tiene lugar en la comunidad.\n\n"
    "Estas reglas son operativas y pueden ampliarse cuando la comunidad defina nuevas normas."
)


class ChieModule(BotModule):
    """Community coordinator: setup, permissions and request notifications."""

    name = "chie"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        self.database = database
        self.topics = ForumTopicService(database)
        self.settings = settings or get_settings()
        self.world = WorldService()
        self.curator = WorldCuratorService(self.world)
        self.curator_ai = WorldCuratorAIService(self.settings)
        self.health = OperatorHealthService()
        self.worker = DurableWorker(database, event_bus=EventBus(), poll_seconds=1.0)
        self.verification = HumanVerificationService()
        self.bot: Bot | None = None
        super().__init__()

    def setup(self) -> None:
        self.router.callback_query.register(self.start_setup, F.data == "chie:setup:start")
        self.router.callback_query.register(self.check_setup, F.data == "chie:setup:check")
        self.router.callback_query.register(self.cancel_setup, F.data == "chie:setup:cancel")
        self.router.callback_query.register(self.command_hub, F.data.startswith("chie:hub:"))
        self.router.message.register(self.configure_group, Command("configurar"))
        self.router.message.register(self.command_hub_command, Command("comandos"))
        self.router.message.register(self.rules_command, Command("reglas"))
        self.router.message.register(self.world_command, Command("mundo"))
        self.router.message.register(self.world_review_command, Command("revisar_mundo"))
        self.router.message.register(self.world_proposal_command, Command("proponer_mundo"))
        self.router.callback_query.register(
            self.world_proposal_decision,
            F.data.startswith("chie:world-proposal:"),
        )
        self.router.message.register(self.health_command, Command("salud"))
        self.router.message.register(self.clear_my_world_data, Command("borrar_mi_memoria"))
        self.router.chat_member.register(self.member_joined)
        self.router.chat_member.register(self.member_left)
        self.router.callback_query.register(self.human_verification, F.data.startswith("chie:verify:"))

    async def on_startup(self, bot: Bot) -> None:
        self.bot = bot
        self.worker.register_event("fan_request.created", self._notify_new_request)
        self.tasks.start("request-notifications", self.worker.run())
        self.tasks.start("world-daily-review", self._daily_world_review_loop())

    async def _notify_new_request(self, payload: dict) -> None:
        if self.bot is None or not self.settings.master_user_id:
            return
        request_id = int(payload["request_id"])
        user_id = int(payload["user_id"])
        chat_id = int(payload["chat_id"])
        description = escape(str(payload.get("description") or ""))
        special_details = escape(str(payload.get("special_details") or ""))
        cost = int(payload.get("points_cost") or 0)
        character = escape(str(payload.get("character_id") or "pendiente"))
        try:
            user = await self.bot.get_chat(user_id)
            display_name = escape(user.full_name)
            username = f" @{escape(user.username)}" if user.username else ""
        except (TelegramBadRequest, TelegramForbiddenError):
            display_name = f"usuario {user_id}"
            username = ""
        try:
            chat = await self.bot.get_chat(chat_id)
            group_title = escape(chat.title or "grupo")
        except (TelegramBadRequest, TelegramForbiddenError):
            group_title = "grupo"
        text = (
            "😰 <b>¡Chie tiene un pedido nuevo!</b>\n\n"
            f"🧾 Pedido <b>#{request_id}</b>\n"
            f"👤 <a href=\"tg://user?id={user_id}\">{display_name}</a>{username}\n"
            f"🏠 {group_title}\n"
            f"💰 Canje: <b>{cost} puntos</b>\n"
            f"🎨 Personaje: <b>{character}</b>\n"
            f"📝 <b>Pedido:</b> {description}"
        )
        if special_details:
            text += f"\n📌 <b>Detalles:</b> {special_details}"
        text += "\n\nCuando tengas la imagen, mandásela a Cami y ella la asociará con este pedido."
        await self.bot.send_message(self.settings.master_user_id, text)

    async def _observe_action(self, action_key: str, user_id: int, chat_id: int | None = None) -> None:
        """Record Chie coordination activity without affecting the main workflow."""
        try:
            async with self.database.session() as session:
                await self.world.observe_action(
                    session,
                    bot_identity=BotIdentity.CHIE,
                    action_key=action_key,
                    user_id=user_id,
                    chat_id=chat_id,
                )
        except Exception:
            logger.exception("World observation failed for Chie action=%s user=%s", action_key, user_id)
    async def member_joined(self, event: ChatMemberUpdated, bot: Bot) -> None:
        old_status = event.old_chat_member.status
        new_member = event.new_chat_member
        if old_status not in {"left", "kicked"}:
            return
        if new_member.status not in {"member", "administrator"}:
            return
        if new_member.user.is_bot:
            return
        if not is_authorized_community(self.settings, event.chat.id):
            return
        async with self.database.session() as session:
            setup = await session.scalar(
                select(SetupSession)
                .where(
                    SetupSession.chat_id == event.chat.id,
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
            )
        if setup is None:
            return
        name = escape(new_member.user.full_name)
        thread_id = await self.topics.get_thread_id(event.chat.id, "bienvenida")
        await bot.send_message(
            event.chat.id,
            f"👋 <b>¡Bienvenido/a, {name}!</b>\n\n"
            "Soy Chie y estoy en la recepción de Ciudad Animals. "
            "Pasá por el tema de <b>reglas</b> antes de empezar. 💛",
            message_thread_id=thread_id,
        ) if thread_id is not None else await bot.send_message(
            event.chat.id,
            f"👋 <b>¡Bienvenido/a, {name}!</b>\n\n"
            "Soy Chie y estoy en la recepción de Ciudad Animals. "
            "Pasá por el tema de <b>reglas</b> antes de empezar. 💛",
        )
        await self._observe_action("welcome", new_member.user.id, event.chat.id)
        await self._start_human_verification(event, bot)
        await self._start_human_verification(event, bot)

    async def _start_human_verification(self, event: ChatMemberUpdated, bot: Bot) -> None:
        user_id = event.new_chat_member.user.id
        chat_id = event.chat.id
        try:
            chat_info = await bot.get_chat(chat_id)
            permissions = getattr(chat_info, "permissions", None)
        except (TelegramBadRequest, TelegramForbiddenError):
            permissions = None

        if permissions is not None:
            try:
                await bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_audios=False,
                        can_send_documents=False,
                        can_send_photos=False,
                        can_send_videos=False,
                        can_send_video_notes=False,
                        can_send_voice_notes=False,
                        can_send_polls=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                    ),
                    use_independent_chat_permissions=True,
                )
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                logger.warning(
                    "Human verification restriction unavailable: chat=%s user=%s error=%s",
                    chat_id,
                    user_id,
                    exc,
                )
                permissions = None

        name = escape(event.new_chat_member.user.full_name)
        prompt = (
            f"🤖 <b>Verificación de {name}</b>\n\n"
            "<b>¿Sos un bot?</b>\n"
            "Elegí una respuesta para habilitar tu participación en la comunidad."
        )
        thread_id = await self.topics.get_thread_id(chat_id, "bienvenida")
        try:
            if thread_id is not None:
                sent = await bot.send_message(
                    chat_id,
                    prompt,
                    message_thread_id=thread_id,
                    reply_markup=chie_human_verification_keyboard(user_id),
                )
            else:
                sent = await bot.send_message(
                    chat_id,
                    prompt,
                    reply_markup=chie_human_verification_keyboard(user_id),
                )
        except (TelegramBadRequest, TelegramForbiddenError):
            logger.exception(
                "Could not send human verification prompt: chat=%s user=%s",
                chat_id,
                user_id,
            )
            return

        async with self.database.session() as session:
            await self.verification.begin(
                session,
                chat_id=chat_id,
                user_id=user_id,
                prompt_message_id=sent.message_id,
                default_permissions_json=permissions_to_json(permissions) if permissions is not None else "{}",
            )
        await self._observe_action("verification_prompt", user_id, chat_id)

    async def human_verification(self, callback: CallbackQuery, bot: Bot) -> None:
        if callback.message is None or callback.from_user is None or not callback.data:
            await callback.answer("Verificación inválida.", show_alert=True)
            return
        parts = callback.data.split(":")
        if len(parts) != 4 or parts[1] != "verify" or parts[2] not in {"yes", "no"}:
            await callback.answer("Verificación inválida.", show_alert=True)
            return
        try:
            target_user_id = int(parts[3])
        except ValueError:
            await callback.answer("Verificación inválida.", show_alert=True)
            return
        if callback.from_user.id != target_user_id:
            await callback.answer("Este botón no es para vos.", show_alert=True)
            return

        chat_id = callback.message.chat.id
        async with self.database.session() as session:
            verification = await session.scalar(
                select(HumanVerification).where(
                    HumanVerification.chat_id == chat_id,
                    HumanVerification.user_id == target_user_id,
                )
            )
        if verification is None or verification.status != "pending":
            await callback.answer("Esta verificación ya fue resuelta.", show_alert=True)
            return

        if parts[2] == "yes":
            try:
                await bot.ban_chat_member(chat_id, target_user_id)
                await bot.unban_chat_member(chat_id, target_user_id)
            except (TelegramBadRequest, TelegramForbiddenError):
                await callback.answer(
                    "No pude expulsarte. Chie necesita permiso para restringir miembros.",
                    show_alert=True,
                )
                return
            async with self.database.session() as session:
                await self.verification.decide(
                    session,
                    chat_id=chat_id,
                    user_id=target_user_id,
                    status="rejected",
                )
            await callback.message.edit_text(
                "🤖 <b>Verificación rechazada.</b>\n"
                "Fuiste expulsado/a de la comunidad. Podés volver a entrar mediante una invitación "
                "y completar la verificación nuevamente."
            )
            await self._observe_action("verification_rejected", target_user_id, chat_id)
            await callback.answer("Expulsión realizada.")
            return

        async with self.database.session() as session:
            decided = await self.verification.decide(
                session,
                chat_id=chat_id,
                user_id=target_user_id,
                status="verified",
            )
        if decided is None:
            await callback.answer("Esta verificación ya fue resuelta.", show_alert=True)
            return

        permissions = permissions_from_json(decided.default_permissions_json)
        if permissions:
            try:
                await bot.restrict_chat_member(
                    chat_id,
                    target_user_id,
                    permissions=ChatPermissions(**permissions),
                    use_independent_chat_permissions=True,
                )
            except (TelegramBadRequest, TelegramForbiddenError):
                logger.exception(
                    "Could not restore verified member permissions: chat=%s user=%s",
                    chat_id,
                    target_user_id,
                )

        await callback.message.edit_text(
            "✅ <b>Verificación completada.</b>\n"
            "Ya podés participar en Ciudad Animals. ¡Bienvenido/a! 💛"
        )
        await self._observe_action("verification_verified", target_user_id, chat_id)
        await callback.answer("Verificado/a. ✅")

    async def member_left(self, event: ChatMemberUpdated, bot: Bot) -> None:
        old_status = getattr(event.old_chat_member.status, "value", event.old_chat_member.status)
        new_status = getattr(event.new_chat_member.status, "value", event.new_chat_member.status)
        if old_status not in {"member", "administrator", "restricted"} or new_status != "left":
            return
        if event.new_chat_member.user.is_bot:
            return
        if not is_authorized_community(self.settings, event.chat.id):
            return
        async with self.database.session() as session:
            verification = await session.scalar(
                select(HumanVerification).where(
                    HumanVerification.chat_id == event.chat.id,
                    HumanVerification.user_id == event.new_chat_member.user.id,
                )
            )
        if verification is not None and verification.status == "rejected":
            return
        name = escape(event.new_chat_member.user.full_name)
        thread_id = await self.topics.get_thread_id(event.chat.id, "bienvenida")
        text = (
            f"👋 <b>Hasta luego, {name}.</b>\n"
            "La puerta del Café Otaku queda abierta si algún día querés volver."
        )
        if thread_id is not None:
            await bot.send_message(event.chat.id, text, message_thread_id=thread_id)
        else:
            await bot.send_message(event.chat.id, text)
        await self._observe_action("farewell", event.new_chat_member.user.id, event.chat.id)

    async def _start_human_verification(self, event: ChatMemberUpdated, bot: Bot) -> None:
        user_id = event.new_chat_member.user.id
        chat_id = event.chat.id
        try:
            chat_info = await bot.get_chat(chat_id)
            permissions = getattr(chat_info, "permissions", None)
        except (TelegramBadRequest, TelegramForbiddenError):
            permissions = None

        if permissions is not None:
            try:
                await bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_audios=False,
                        can_send_documents=False,
                        can_send_photos=False,
                        can_send_videos=False,
                        can_send_video_notes=False,
                        can_send_voice_notes=False,
                        can_send_polls=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                    ),
                    use_independent_chat_permissions=True,
                )
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                logger.warning(
                    "Could not restrict new member for human verification: chat=%s user=%s error=%s",
                    chat_id,
                    user_id,
                    exc,
                )
                permissions = None

        name = escape(event.new_chat_member.user.full_name)
        prompt = (
            f"🤖 <b>Verificación de {name}</b>\n\n"
            "<b>¿Sos un bot?</b>\n"
            "Elegí una sola respuesta para poder participar en la comunidad."
        )
        thread_id = await self.topics.get_thread_id(chat_id, "bienvenida")
        try:
            kwargs = {"message_thread_id": thread_id} if thread_id is not None else {}
            sent = await bot.send_message(
                chat_id,
                prompt,
                reply_markup=chie_human_verification_keyboard(user_id),
                **kwargs,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            logger.exception(
                "Could not send human verification prompt: chat=%s user=%s",
                chat_id,
                user_id,
            )
            return

        async with self.database.session() as session:
            await self.verification.begin(
                session,
                chat_id=chat_id,
                user_id=user_id,
                prompt_message_id=sent.message_id,
                default_permissions_json=(
                    permissions_to_json(permissions) if permissions is not None else "{}"
                ),
            )
        await self._observe_action("verification_prompt", user_id, chat_id)

    async def human_verification(self, callback: CallbackQuery, bot: Bot) -> None:
        if callback.message is None or callback.from_user is None or not callback.data:
            await callback.answer("Verificación inválida.", show_alert=True)
            return
        parts = callback.data.split(":")
        if len(parts) != 4 or parts[1] != "verify" or parts[2] not in {"yes", "no"}:
            await callback.answer("Verificación inválida.", show_alert=True)
            return
        try:
            target_user_id = int(parts[3])
        except ValueError:
            await callback.answer("Verificación inválida.", show_alert=True)
            return
        if callback.from_user.id != target_user_id:
            await callback.answer("Este botón no es para vos.", show_alert=True)
            return

        chat_id = callback.message.chat.id
        async with self.database.session() as session:
            verification = await session.scalar(
                select(HumanVerification).where(
                    HumanVerification.chat_id == chat_id,
                    HumanVerification.user_id == target_user_id,
                )
            )
        if verification is None or verification.status != "pending":
            await callback.answer("Esta verificación ya fue resuelta.", show_alert=True)
            return

        if parts[2] == "yes":
            try:
                await bot.ban_chat_member(chat_id, target_user_id)
                await bot.unban_chat_member(chat_id, target_user_id)
            except (TelegramBadRequest, TelegramForbiddenError):
                await callback.answer(
                    "No pude expulsarte. Chie necesita permiso para restringir miembros.",
                    show_alert=True,
                )
                return
            async with self.database.session() as session:
                await self.verification.decide(
                    session,
                    chat_id=chat_id,
                    user_id=target_user_id,
                    status="rejected",
                )
            await callback.message.edit_text(
                "🤖 <b>Verificación rechazada.</b>\n"
                "Fuiste expulsado/a. Podés volver a entrar mediante una invitación y completar la verificación nuevamente."
            )
            await self._observe_action("verification_rejected", target_user_id, chat_id)
            await callback.answer("Expulsión realizada.")
            return

        async with self.database.session() as session:
            decided = await self.verification.decide(
                session,
                chat_id=chat_id,
                user_id=target_user_id,
                status="verified",
            )
        if decided is None:
            await callback.answer("Esta verificación ya fue resuelta.", show_alert=True)
            return

        permissions = permissions_from_json(decided.default_permissions_json)
        if permissions:
            try:
                await bot.restrict_chat_member(
                    chat_id,
                    target_user_id,
                    permissions=ChatPermissions(**permissions),
                    use_independent_chat_permissions=True,
                )
            except (TelegramBadRequest, TelegramForbiddenError):
                logger.exception(
                    "Could not restore verified member permissions: chat=%s user=%s",
                    chat_id,
                    target_user_id,
                )

        await callback.message.edit_text(
            "✅ <b>Verificación completada.</b>\n"
            "Ya podés participar en Ciudad Animals. ¡Bienvenido/a! 💛"
        )
        await self._observe_action("verification_verified", target_user_id, chat_id)
        await callback.answer("Verificado/a. ✅")

    async def member_left(self, event: ChatMemberUpdated, bot: Bot) -> None:
        old_status = getattr(event.old_chat_member.status, "value", event.old_chat_member.status)
        new_status = getattr(event.new_chat_member.status, "value", event.new_chat_member.status)
        if old_status not in {"member", "administrator", "restricted"} or new_status != "left":
            return
        if event.new_chat_member.user.is_bot:
            return
        if not is_authorized_community(self.settings, event.chat.id):
            return
        async with self.database.session() as session:
            verification = await session.scalar(
                select(HumanVerification).where(
                    HumanVerification.chat_id == event.chat.id,
                    HumanVerification.user_id == event.new_chat_member.user.id,
                )
            )
        if verification is not None and verification.status == "rejected":
            return
        name = escape(event.new_chat_member.user.full_name)
        thread_id = await self.topics.get_thread_id(event.chat.id, "bienvenida")
        text = (
            f"👋 <b>Hasta luego, {name}.</b>\n"
            "La puerta del Café Otaku queda abierta si algún día querés volver."
        )
        if thread_id is not None:
            await bot.send_message(event.chat.id, text, message_thread_id=thread_id)
        else:
            await bot.send_message(event.chat.id, text)
        await self._observe_action("farewell", event.new_chat_member.user.id, event.chat.id)
    async def rules_command(self, message: Message) -> None:
        if message.chat.type not in {"group", "supergroup"}:
            return
        await message.answer(COMMUNITY_RULES)
        if message.from_user is not None:
            await self._observe_action("rules_view", message.from_user.id, message.chat.id)

    async def start_setup(self, callback: CallbackQuery) -> None:
        if not callback.message or callback.message.chat.type != "private":
            await callback.answer("Abrime en privado para iniciar la configuración.", show_alert=True)
            return
        await callback.answer()
        await self._observe_action("onboarding_start", callback.from_user.id)
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
            return
        if not await is_chat_staff(message, bot):
            return
        member = await bot.get_chat_member(message.chat.id, bot.id)
        if not isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            await message.answer("😰 Necesito ser administradora del grupo antes de reformarlo.")
            return
        missing = [label for attr, label in REQUIRED_ADMIN_PERMISSIONS.items() if not getattr(member, attr, False)]
        if missing:
            await message.answer("Me faltan estos permisos: " + ", ".join(missing) + ".")
            return
        async with self.database.session() as session:
            existing = await session.scalar(select(SetupSession).where(
                SetupSession.user_id == message.from_user.id,
                SetupSession.bot_identity == BotIdentity.CHIE.value,
            ))
            if existing:
                existing.chat_id = message.chat.id
                existing.status = "awaiting_confirmation"
            else:
                session.add(SetupSession(
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    bot_identity=BotIdentity.CHIE.value,
                    status="awaiting_confirmation",
                ))
            await session.commit()
        await message.answer(
            f"✅ Permisos comprobados.\n\n"
            f"🆔 ID de esta comunidad: <code>{message.chat.id}</code>\n\n"
            "Copiá ese ID en Bot Manager como Grupo general / bienvenida y agregalo a AUTHORIZED_CHAT_IDS.\n"
            "Después volvé al chat privado conmigo y tocá <b>Ya me agregaste de admin</b>."
        )
        await self._observe_action("onboarding_group_configured", message.from_user.id, message.chat.id)

    async def check_setup(self, callback: CallbackQuery, bot: Bot) -> None:
        if not callback.from_user or not callback.message:
            return
        async with self.database.session() as session:
            setup = await session.scalar(select(SetupSession).where(
                SetupSession.user_id == callback.from_user.id,
                SetupSession.bot_identity == BotIdentity.CHIE.value,
                SetupSession.status == "awaiting_confirmation",
            ))
            if not setup:
                await callback.answer("Primero ejecutá /configurar dentro del grupo.", show_alert=True)
                return
            chat_id = setup.chat_id
        if not any(
            self.settings.is_chat_allowed(chat_id, chat_type)
            for chat_type in ("group", "supergroup")
        ):
            await callback.answer(
                "Esta comunidad todavía no está autorizada. Agregá su ID a AUTHORIZED_CHAT_IDS antes de continuar.",
                show_alert=True,
            )
            return
        member = await bot.get_chat_member(chat_id, bot.id)
        missing = [] if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)) else list(REQUIRED_ADMIN_PERMISSIONS.values())
        if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            missing = [label for attr, label in REQUIRED_ADMIN_PERMISSIONS.items() if not getattr(member, attr, False)]
        if missing:
            await callback.answer("Todavía me faltan: " + ", ".join(missing), show_alert=True)
            return
        topic_keys = ("comandos", "bienvenida", "reglas", "noticias", "undiacomohoy", "recomendaciondiaria", "curiosidades", "estrenos", "memes", "material", "anime", "debates", "trivia", "waifumon", "puntos", "pedidos")
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
        if not failures:
            try:
                commands_thread = await self.topics.get_thread_id(chat_id, "comandos")
                if commands_thread is not None:
                    await bot.send_message(chat_id, "🤖 <b>Panel de la comunidad</b>\nLos botones son el acceso rápido.", message_thread_id=commands_thread, reply_markup=command_hub_keyboard())
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                failures.append(f"publicar panel: {exc}")
        async with self.database.session() as session:
            setup = await session.scalar(select(SetupSession).where(
                SetupSession.user_id == callback.from_user.id,
                SetupSession.bot_identity == BotIdentity.CHIE.value,
            ))
            if setup:
                setup.status = "configured" if not failures else "partial"
                await session.commit()
        await callback.answer("Configuración terminada." if not failures else "Configuración parcial.")
        text = f"🎉 <b>Chie ya está trabajando.</b>\nTemas creados en esta pasada: {created}."
        if failures:
            text += "\n\n⚠️ Me detuve porque Telegram rechazó una operación. Revisá permisos y que el grupo sea un supergrupo con Foro activado."
        await callback.message.edit_text(text, reply_markup=command_hub_keyboard())
        await self._observe_action("onboarding_confirmed" if not failures else "onboarding_partial", callback.from_user.id, chat_id)

    async def cancel_setup(self, callback: CallbackQuery) -> None:
        if callback.message:
            await callback.message.edit_text("Configuración cancelada. Cuando quieras, tocá /start y volvemos a intentarlo.")
        await callback.answer()

    async def world_command(self, message: Message) -> None:
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.from_user.id != self.settings.master_user_id
        ):
            return
        lines = ["🌍 <b>Ciudad Animals — estado agregado</b>", ""]
        async with self.database.session() as session:
            for identity in BotIdentity:
                insights = await self.world.insights(session, bot_identity=identity)
                lines.append(f"<b>{identity.value.title()}</b>")
                if insights.hot:
                    lines.append("🔥 " + ", ".join(f"{key} ({count})" for key, count in insights.hot[:3]))
                if insights.cold:
                    lines.append("❄️ " + ", ".join(f"{key} ({count})" for key, count in insights.cold[:3]))
                if insights.unseen:
                    lines.append("👀 " + ", ".join(key for key, _ in insights.unseen[:3]))
                if not insights.hot and not insights.cold and not insights.unseen:
                    lines.append("· sin datos todavía")
                lines.append("")
        await message.answer("\n".join(lines))

    async def _daily_world_review_loop(self) -> None:
        last_day: str | None = None
        while True:
            day_key = world_now(self.settings.bot_world_timezone).date().isoformat()
            if day_key != last_day:
                try:
                    async with self.database.session() as session:
                        report = await self.curator.build_daily(
                            session,
                            day_key=day_key,
                        )
                    last_day = report.period_key
                    logger.info("Ciudad Animals daily review ready: day=%s", day_key)
                    await self._maybe_generate_daily_world_proposal(
                        day_key=day_key,
                        report=report,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Failed to build Ciudad Animals daily review: day=%s",
                        day_key,
                    )
            await asyncio.sleep(900)

    async def _maybe_generate_daily_world_proposal(
        self,
        *,
        day_key: str,
        report,
    ) -> None:
        """Generate an optional daily proposal from aggregate data only."""
        if not self.settings.ai_curator_auto:
            return
        if not self.settings.ai_for(BotIdentity.CHIE):
            return
        if not self.settings.master_user_id or self.bot is None:
            return

        async with self.database.session() as session:
            review_row = await session.scalar(
                select(WorldReview).where(
                    WorldReview.review_type == self.curator.DAILY,
                    WorldReview.period_key == day_key,
                )
            )
            if review_row is None:
                raise RuntimeError("Daily world review was not persisted")
            existing = await session.scalar(
                select(WorldProposal).where(
                    WorldProposal.review_id == review_row.id,
                    WorldProposal.generator == self.curator_ai._generator_name(),
                )
            )
            if existing is not None:
                return
            review_id = review_row.id

        proposals = await self.curator_ai.propose_for_database(
            self.database,
            review_id=review_id,
            report=report,
        )
        await self.bot.send_message(
            self.settings.master_user_id,
            format_world_proposals(proposals),
            reply_markup=world_proposal_keyboard(proposals.proposal_id),
        )

    async def world_review_command(self, message: Message) -> None:
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.from_user.id != self.settings.master_user_id
        ):
            return
        day_key = world_now(self.settings.bot_world_timezone).date().isoformat()
        async with self.database.session() as session:
            report = await self.curator.build_daily(
                session,
                day_key=day_key,
            )
        await message.answer(format_world_review(report))
    async def world_proposal_command(self, message: Message) -> None:
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.from_user.id != self.settings.master_user_id
        ):
            return
        day_key = world_now(self.settings.bot_world_timezone).date().isoformat()
        try:
            async with self.database.session() as session:
                report = await self.curator.build_daily(
                    session,
                    day_key=day_key,
                )
                review_row = await session.scalar(
                    select(WorldReview).where(
                        WorldReview.review_type == self.curator.DAILY,
                        WorldReview.period_key == day_key,
                    )
                )
                if review_row is None:
                    raise RuntimeError("Daily world review was not persisted")
                review_id = review_row.id
            proposals = await self.curator_ai.propose_for_database(
                self.database,
                review_id=review_id,
                report=report,
            )
            await message.answer(
                format_world_proposals(proposals),
                reply_markup=world_proposal_keyboard(proposals.proposal_id),
            )
        except Exception as exc:
            logger.exception("Failed to generate world proposals")
            await message.answer(f"⚠️ No se pudieron generar propuestas: {exc}")
    async def world_proposal_decision(
        self,
        callback: CallbackQuery,
    ) -> None:
        if (
            callback.message is None
            or callback.from_user is None
            or callback.from_user.id != self.settings.master_user_id
            or callback.message.chat.type != "private"
            or callback.message.chat.id != self.settings.master_user_id
        ):
            await callback.answer("No autorizado.", show_alert=True)
            return

        parts = (callback.data or "").split(":")
        if len(parts) != 4 or parts[2] not in {"accept", "reject"} or not parts[3]:
            await callback.answer("Propuesta inválida.", show_alert=True)
            return
        try:
            proposal_id = int(parts[3])
        except ValueError:
            await callback.answer("Propuesta inválida.", show_alert=True)
            return

        async with self.database.session() as session:
            accepted = await self.curator_ai.decide(
                session,
                proposal_id=proposal_id,
                approved=parts[2] == "accept",
            )
            if not accepted:
                await callback.answer(
                    "La propuesta ya fue revisada o no existe.",
                    show_alert=True,
                )
                return

        status = "aceptada" if parts[2] == "accept" else "rechazada"
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"📌 Propuesta #{proposal_id} {status}. "
            "La decisión no modifica automáticamente el canon ni el código."
        )
        await callback.answer("Decisión guardada.")

    async def health_command(self, message: Message) -> None:
        """Show a read-only system health snapshot to the configured owner."""
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.from_user.id != self.settings.master_user_id
        ):
            return
        async with self.database.session() as session:
            snapshot = await self.health.snapshot(
                session,
                authorized_chat_ids=self.settings.authorized_chat_ids_set,
            )
        await message.answer(format_operator_health(snapshot))

    async def clear_my_world_data(self, message: Message) -> None:
        """Let a user erase their private world-usage statistics."""
        if message.chat.type != "private" or message.from_user is None:
            return
        async with self.database.session() as session:
            deleted = await self.world.clear_user_statistics(
                session,
                user_id=message.from_user.id,
            )
        await message.answer(
            "🧹 <b>Memoria estadística borrada.</b>\n"
            f"Se eliminaron {deleted} registros privados de uso de Ciudad Animals.\n"
            "Los agregados globales no se pueden reconstruir hacia vos y no se modificaron."
        )

    async def command_hub_command(self, message: Message, bot: Bot) -> None:
        if message.chat.type != "private" and not await is_chat_staff(message, bot):
            return
        await message.answer("🤖 <b>Panel de la comunidad</b>\nElegí qué querés hacer.", reply_markup=command_hub_keyboard())

    async def command_hub(self, callback: CallbackQuery) -> None:
        if not callback.message:
            return
        section = (callback.data or "").rsplit(":", 1)[-1]
        if section == "home":
            await callback.message.edit_text(
                "🤖 <b>Panel de la comunidad</b>\nElegí un área para ver acciones concretas.",
                reply_markup=command_hub_keyboard(),
            )
            await callback.answer()
            return

        details = {
            "community": (
                "👋 <b>Comunidad</b>\n\n"
                "• <code>/reglas</code> — reglas operativas.\n"
                "• <code>/salud</code> — diagnóstico del administrador.\n"
                "• Chie da la bienvenida a nuevos integrantes autorizados.\n"
                "• La moderación se ejecuta con permisos reales de Telegram."
            ),
            "games": (
                "🎮 <b>Juegos</b>\n\n"
                "En el bot de Sunna:\n"
                "• <code>/juego</code> — panel de juegos.\n"
                "• <code>/gacha</code> — tirada local.\n"
                "• <code>/inventario</code> — colección y evolución.\n"
                "• <code>/combate</code> — combate.\n"
                "• <code>/trivia</code> — estado de trivia.\n"
                "• <code>/puntos</code> / <code>/ranking</code> — economía comunitaria.\n\n"
                "La aparición pública de WaifuMon ocurre solo en la comunidad configurada."
            ),
            "content": (
                "📰 <b>Contenido</b>\n\n"
                "En el bot de Cami:\n"
                "• <code>/catalogo</code> — material local.\n"
                "• <code>/anime</code> — fichas locales.\n"
                "• <code>/anime_ficha</code> — detalle de una obra.\n"
                "• <code>/recuperar_publicaciones</code> — recuperación para administración.\n\n"
                "Cami no completa registros faltantes con IA."
            ),
            "points": (
                "💰 <b>Puntos y pedidos</b>\n\n"
                "• Consultá <code>/puntos</code> con Sunna.\n"
                "• <code>/ranking</code> muestra la situación comunitaria.\n"
                "• El botón <b>🎨 Pedir imagen</b> inicia el pedido desde este panel.\n"
                "• Los pedidos cobran puntos dentro de una transacción idempotente."
            ),
            "config": (
                "⚙️ <b>Configuración</b>\n\n"
                "• <code>/configurar</code> verifica administración real y prepara los temas del foro.\n"
                "• <code>/salud</code> muestra un diagnóstico agregado al administrador.\n"
                "• <code>/mundo</code> y <code>/revisar_mundo</code> muestran el estado agregado de Ciudad Animals.\n"
                "• <code>/proponer_mundo</code> puede usar IA como curadora, nunca como autoridad automática del canon."
            ),
        }
        text = details.get(section)
        if text is None:
            await callback.answer("Sección no disponible.", show_alert=True)
            return
        await callback.message.edit_text(
            text,
            reply_markup=command_hub_detail_keyboard(),
        )
        if callback.from_user is not None:
            await self._observe_action(f"hub_{section}", callback.from_user.id, callback.message.chat.id)
        await callback.answer()
