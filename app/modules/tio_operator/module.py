from __future__ import annotations

from html import escape

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.operator import is_tio_addressed
from app.core.module import BotModule
from app.db.database import Database
from app.db.models import TioOperatorRequest
from app.services.tio_operator import TioOperatorService
from app.ui.control_keyboards import tio_operator_request_keyboard, tio_operator_resolve_keyboard


class TioOperatorModule(BotModule):
    """Human-operator bridge; never composes a reply as Tío Otaku."""

    name = "tio-operator"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.service = TioOperatorService()

    def setup(self) -> None:
        self.router.message.register(
            self.pending_command,
            Command("tio_pendientes"),
        )
        self.router.message.register(
            self.respond_command,
            Command("tio_responder"),
        )
        self.router.message.register(
            self.capture_message,
            F.text.func(self._should_capture),
        )
        self.router.callback_query.register(
            self.decide_request,
            F.data.startswith("tio:request:"),
        )

    def _should_capture(self, text: str) -> bool:
        return is_tio_addressed(text)

    @staticmethod
    def _is_owner_private(message: Message, settings: Settings) -> bool:
        return (
            message.chat.type == "private"
            and message.from_user is not None
            and message.chat.id == settings.admin_user_id
            and message.from_user.id == settings.admin_user_id
        )

    async def pending_command(self, message: Message) -> None:
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.chat.id != self.settings.admin_user_id
            or message.from_user.id != self.settings.admin_user_id
        ):
            return

        async with self.database.session() as session:
            requests = await self.service.recent_pending(session, limit=10)
            if not requests:
                await message.answer("📭 No hay solicitudes pendientes para Tío Otaku.")
                return

            for request in requests:
                user, chat = await self.service.context(session, request)
                user_name = (
                    escape(user.first_name or str(request.user_id))
                    if user
                    else str(request.user_id)
                )
                chat_name = (
                    escape(chat.title or str(request.chat_id))
                    if chat
                    else str(request.chat_id)
                )
                status_label = {
                    "pending": "🆕 pendiente",
                    "acknowledged": "👀 recibida",
                    "responding": "⏳ respondiendo",
                }.get(request.status, escape(request.status))
                keyboard = (
                    tio_operator_resolve_keyboard(request.id)
                    if request.status == "responding"
                    else tio_operator_request_keyboard(request.id)
                )
                await message.answer(
                    f"📨 <b>Solicitud #{request.id}</b> · {status_label}\n"
                    f"👤 {user_name} · 🏠 {chat_name}\n"
                    f"{escape(request.text[:1000])}",
                    reply_markup=keyboard,
                )

    async def respond_command(self, message: Message, bot: Bot) -> None:
        """Relay the operator's exact text to the original community request."""
        if not self._is_owner_private(message, self.settings) or not message.text:
            return

        parts = message.text.split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit():
            await message.answer(
                "Uso: <code>/tio_responder ID mensaje</code>",
            )
            return

        request_id = int(parts[1])
        reply_text = parts[2].strip()
        if not reply_text:
            await message.answer("La respuesta no puede estar vacía.")
            return

        async with self.database.session(write=True) as session:
            request = await session.get(TioOperatorRequest, request_id)
            if request is None or request.status not in {"pending", "acknowledged"}:
                await message.answer("Esa solicitud no está pendiente de respuesta.")
                return

            if not is_authorized_community(self.settings, request.chat_id):
                await message.answer(
                    "La comunidad original ya no está autorizada; no voy a enviar el mensaje.",
                )
                return

            if not await self.service.claim_response(
                session,
                request_id=request_id,
            ):
                await message.answer(
                    f"⏳ La solicitud #{request_id} ya está siendo respondida o procesada.",
                )
                return
            destination = request.chat_id
            source_user = request.user_id

        try:
            await bot.send_message(
                destination,
                f"💬 <b>Tío Otaku (operador humano)</b>\n\n{escape(reply_text)}",
            )
        except Exception:
            async with self.database.session(write=True) as session:
                await self.service.release_response(
                    session,
                    request_id=request_id,
                )
            await message.answer(
                f"❌ No pude entregar la respuesta de la solicitud #{request_id}. "
                "La solicitud volvió a quedar disponible."
            )
            raise

        async with self.database.session(write=True) as session:
            resolved = await self.service.decide(
                session,
                request_id=request_id,
                status="resolved",
            )
            if not resolved:
                await message.answer(
                    f"⚠️ La respuesta de la solicitud #{request_id} fue enviada, "
                    "pero el estado quedó para revisión manual.",
                )
                return

        await message.answer(
            f"✅ Respuesta de la solicitud #{request_id} enviada a la comunidad "
            f"(usuario {source_user}).",
        )

    async def capture_message(self, message: Message, bot: Bot) -> None:
        if (
            message.from_user is None
            or message.from_user.is_bot
            or not message.text
            or message.chat.type not in {"group", "supergroup"}
            or not is_authorized_community(self.settings, message.chat.id)
            or not self.settings.admin_user_id
        ):
            return

        async with self.database.session() as session:
            result = await self.service.capture(
                session,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                source_message_id=message.message_id,
                text=message.text,
            )

        if not result.created:
            return

        user_name = escape(message.from_user.full_name)
        chat_title = escape(message.chat.title or str(message.chat.id))
        source_text = escape(message.text)
        await bot.send_message(
            self.settings.admin_user_id,
            (
                "📨 <b>Solicitud para Tío Otaku</b>\n\n"
                f"👤 {user_name} · <code>{message.from_user.id}</code>\n"
                f"🏠 {chat_title} · <code>{message.chat.id}</code>\n"
                f"🧾 Solicitud <b>#{result.request.id}</b>\n\n"
                f"<b>Mensaje:</b> {source_text}\n\n"
                "Tío Otaku es un operador humano: el sistema solo transporta la solicitud."
            ),
            reply_markup=tio_operator_request_keyboard(result.request.id),
        )

    async def decide_request(self, callback: CallbackQuery) -> None:
        if (
            callback.message is None
            or callback.from_user is None
            or callback.from_user.id != self.settings.admin_user_id
            or not self._is_owner_private(callback.message, self.settings)
        ):
            await callback.answer("No autorizado.", show_alert=True)
            return

        parts = (callback.data or "").split(":")
        if len(parts) != 4 or parts[2] not in {"ack", "resolve"}:
            await callback.answer("Solicitud inválida.", show_alert=True)
            return

        try:
            request_id = int(parts[3])
        except ValueError:
            await callback.answer("Solicitud inválida.", show_alert=True)
            return

        status = "acknowledged" if parts[2] == "ack" else "resolved"
        async with self.database.session() as session:
            changed = await self.service.decide(
                session,
                request_id=request_id,
                status=status,
            )

        if not changed:
            await callback.answer(
                "Solicitud ya procesada o inexistente.",
                show_alert=True,
            )
            return

        label = "recibida" if status == "acknowledged" else "resuelta"
        if status == "acknowledged":
            await callback.message.edit_reply_markup(
                reply_markup=tio_operator_resolve_keyboard(request_id),
            )
        else:
            await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"📝 Solicitud #{request_id} marcada como {label}. "
            "El sistema no redacta ni envía una respuesta como Tío Otaku."
        )
        await callback.answer("Estado actualizado.")
