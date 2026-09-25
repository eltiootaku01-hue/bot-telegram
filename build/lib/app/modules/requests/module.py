from html import escape
import logging

from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.database import Database
from app.db.models import GameProfile, RequestStatus
from app.services.requests import DEFAULT_REQUEST_COST, RequestService
from app.services.world import WorldService
from app.ui.control_keyboards import chie_request_cancel_keyboard

logger = logging.getLogger(__name__)


class RequestStates(StatesGroup):
    waiting_description = State()


class RequestModule(BotModule):
    """Public button-first intake for paid fan image requests."""

    name = "requests"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.service = RequestService()
        self.world = WorldService()

    def setup(self) -> None:
        self.router.callback_query.register(self.start_request, F.data == "chie:request:start")
        self.router.callback_query.register(self.cancel_request, F.data == "chie:request:cancel")
        self.router.message.register(self.receive_description, RequestStates.waiting_description)
        self.router.message.register(self.my_requests, Command("mis_pedidos"))

    async def _observe_action(self, action_key: str, user_id: int, chat_id: int) -> None:
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
            logger.exception("World observation failed for Chie request action=%s user=%s", action_key, user_id)

    async def start_request(self, callback: CallbackQuery, state: FSMContext) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer("No pude iniciar el pedido.", show_alert=True)
            return
        if callback.message.chat.type not in {"group", "supergroup"}:
            await callback.answer("Los pedidos se hacen desde el grupo.", show_alert=True)
            return
        async with self.database.session() as session:
            profile = await session.scalar(
                select(GameProfile).where(
                    GameProfile.user_id == callback.from_user.id,
                    GameProfile.chat_id == callback.message.chat.id,
                )
            )
            balance = profile.points if profile else 0
        if balance < DEFAULT_REQUEST_COST:
            await callback.answer(
                f"Necesitás {DEFAULT_REQUEST_COST} puntos y tenés {balance}.",
                show_alert=True,
            )
            return
        await state.set_state(RequestStates.waiting_description)
        await callback.message.answer(
            f"🎨 <b>Pedido de imagen</b>\n\n"
            f"Costo: <b>{DEFAULT_REQUEST_COST} puntos</b>.\n"
            "Escribí qué imagen querés. Podés indicar personaje, ropa, pose, estilo y cualquier detalle necesario.\n\n"
            "Ejemplo: <i>Asuna con traje de conejita, fondo nocturno, estilo ilustración</i>",
            reply_markup=chie_request_cancel_keyboard(),
        )
        await callback.answer()
        await self._observe_action("request_start", callback.from_user.id, callback.message.chat.id)

    async def my_requests(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return

        async with self.database.session() as session:
            requests = await self.service.for_user(
                session,
                user_id=message.from_user.id,
                limit=10,
            )

        if not requests:
            await message.answer("📭 Todavía no tenés pedidos registrados.")
            return

        labels = {
            RequestStatus.NEW.value: "nuevo",
            RequestStatus.NEEDS_INFO.value: "necesita datos",
            RequestStatus.PENDING_ADMIN.value: "en cola",
            RequestStatus.APPROVED.value: "aprobado",
            RequestStatus.SCHEDULED.value: "programado",
            RequestStatus.PROCESSING.value: "procesando",
            RequestStatus.COMPLETED.value: "completado",
            RequestStatus.REJECTED.value: "rechazado",
            RequestStatus.CANCELLED.value: "cancelado",
        }
        lines = ["📋 <b>Tus últimos pedidos</b>", ""]
        for request in requests:
            status = labels.get(request.status, request.status)
            due = (
                request.due_at.strftime("%d/%m %H:%M")
                if request.due_at is not None
                else "sin fecha"
            )
            description = escape(request.description[:90])
            lines.append(f"• <b>#{request.id}</b> · {status} · vence: {due}")
            lines.append(f"  {description}")
        lines.extend(("", "Podés consultar esta lista cuando quieras; el historial se conserva aunque el bot se reinicie."))
        await message.answer("\n".join(lines))

    async def receive_description(self, message: Message, state: FSMContext) -> None:
        if message.chat.type not in {"group", "supergroup"} or message.from_user is None or not message.text:
            return
        description = message.text.strip()
        if len(description) < 4:
            await message.answer("🎨 Necesito un poco más de detalle para crear el pedido.")
            return
        async with self.database.session(write=True) as session:
            result = await self.service.create_paid(
                session,
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                description=description,
                points_cost=DEFAULT_REQUEST_COST,
                source_message_id=message.message_id,
            )
        await state.clear()
        if result is None:
            await message.answer("😰 No pude cobrar el pedido: ya no tenés suficientes puntos.")
            await self._observe_action("request_rejected_no_points", message.from_user.id, message.chat.id)
            return
        request = result.request
        if not result.created:
            await message.answer(
                f"ℹ️ <b>Pedido #{request.id} ya estaba registrado.</b>\n"
                f"No se volvieron a descontar puntos. Saldo actual: <b>{result.remaining_points}</b>."
            )
            await self._observe_action("request_replay", message.from_user.id, message.chat.id)
            return
        await message.answer(
            f"✅ <b>Pedido #{request.id} registrado.</b>\n"
            f"💰 Se descontaron {DEFAULT_REQUEST_COST} puntos. Saldo restante: <b>{result.remaining_points}</b>.\n\n"
            "Chie ya avisó al encargado. Cuando la imagen esté lista, Cami la llevará a #pedidos y te etiquetará.",
        )
        await self._observe_action("request_created", message.from_user.id, message.chat.id)

    async def cancel_request(self, callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        if callback.message:
            await callback.message.edit_text("↩️ Pedido cancelado. No se descontaron puntos.")
        await callback.answer()
