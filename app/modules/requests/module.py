from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.module import BotModule
from app.db.database import Database
from app.db.models import GameProfile
from app.services.requests import DEFAULT_REQUEST_COST, RequestService
from app.ui.control_keyboards import chie_request_cancel_keyboard


class RequestStates(StatesGroup):
    waiting_description = State()


class RequestModule(BotModule):
    """Public button-first intake for paid fan image requests."""

    name = "requests"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.service = RequestService()

    def setup(self) -> None:
        self.router.callback_query.register(self.start_request, F.data == "chie:request:start")
        self.router.callback_query.register(self.cancel_request, F.data == "chie:request:cancel")
        self.router.message.register(self.receive_description, RequestStates.waiting_description)

    async def start_request(self, callback: CallbackQuery, state: FSMContext) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer("No pude iniciar el pedido.", show_alert=True)
            return
        if callback.message.chat.type not in {"group", "supergroup"}:
            await callback.answer("Los pedidos se hacen desde el grupo.", show_alert=True)
            return
        async with self.database.session() as session:
            profile = await session.scalar(select(GameProfile).where(
                GameProfile.user_id == callback.from_user.id,
                GameProfile.chat_id == callback.message.chat.id,
            ))
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

    async def receive_description(self, message: Message, state: FSMContext) -> None:
        if message.chat.type not in {"group", "supergroup"} or message.from_user is None or not message.text:
            return
        description = message.text.strip()
        if len(description) < 4:
            await message.answer("🎨 Necesito un poco más de detalle para crear el pedido.")
            return
        async with self.database.session() as session:
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
            return
        request, remaining = result
        await message.answer(
            f"✅ <b>Pedido #{request.id} registrado.</b>\n"
            f"💰 Se descontaron {DEFAULT_REQUEST_COST} puntos. Saldo restante: <b>{remaining}</b>.\n\n"
            "Chie ya avisó al encargado. Cuando la imagen esté lista, Cami la llevará a #pedidos y te etiquetará.",
        )

    async def cancel_request(self, callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        if callback.message:
            await callback.message.edit_text("↩️ Pedido cancelado. No se descontaron puntos.")
        await callback.answer()
