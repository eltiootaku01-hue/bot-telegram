from __future__ import annotations

import logging

from aiogram import Bot, F
from sqlalchemy import select
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from app.core.config import Settings, get_settings
from app.core.module import BotModule
from app.db.database import Database
from app.db.models import RareDropApproval, WaifuGiftDrop
from app.game.catalog import get_character
from app.game.gacha import GachaService
from app.game.rare_approval import decide
from app.game.waifu_gifts import WaifuGiftService
from app.ui.control_keyboards import gift_delivery_recovery_keyboard, rare_approval_keyboard

logger = logging.getLogger(__name__)


class AdminModule(BotModule):
    """Owner-only workflows for exceptional drops."""

    name = "admin"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.gacha = GachaService()
        self.gifts = WaifuGiftService()

    def setup(self) -> None:
        self.router.message.register(
            self.pending_approvals_command,
            Command("gacha_pendientes"),
        )
        self.router.callback_query.register(
            self.rare_decision,
            F.data.startswith("admin:rare:"),
        )
        self.router.message.register(
            self.unknown_gifts_command,
            Command("regalos_pendientes"),
        )
        self.router.callback_query.register(
            self.gift_delivery_recovery,
            F.data.startswith("admin:gift:"),
        )

    def _is_owner(self, callback: CallbackQuery) -> bool:
        return (
            bool(self.settings.master_user_id)
            and callback.from_user.id == self.settings.master_user_id
            and callback.message is not None
            and callback.message.chat.type == "private"
            and callback.message.chat.id == self.settings.master_user_id
        )

    async def pending_approvals_command(self, message: Message) -> None:
        """Show pending rare-drop approvals so lost notifications remain recoverable."""
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.chat.id != self.settings.master_user_id
            or message.from_user.id != self.settings.master_user_id
        ):
            return

        async with self.database.session() as session:
            approvals = list(
                await session.scalars(
                    select(RareDropApproval)
                    .where(RareDropApproval.status == "pending")
                    .order_by(RareDropApproval.id.asc())
                    .limit(20)
                )
            )

        if not approvals:
            await message.answer("✅ No hay drops raros pendientes de aprobación.")
            return

        await message.answer(
            f"🌟 <b>Drops raros pendientes: {len(approvals)}</b>\n"
            "Cada elemento conserva su decisión hasta que la apruebes o rechaces."
        )
        for approval in approvals:
            character = get_character(approval.character_id)
            await message.answer(
                f"🌟 <b>Solicitud #{approval.id}</b>\n"
                f"Jugador: <code>{approval.target_user_id}</code>\n"
                f"Comunidad: <code>{approval.target_chat_id}</code>\n"
                f"Personaje: <b>{character.name}</b>\n"
                f"Rareza: <b>{approval.rarity}</b>",
                reply_markup=rare_approval_keyboard(approval.id),
            )


    async def unknown_gifts_command(self, message: Message) -> None:
        """List Sunna gift sends whose Telegram outcome was ambiguous."""
        if (
            message.chat.type != "private"
            or message.from_user is None
            or not self.settings.is_master(message.from_user.id)
        ):
            return

        async with self.database.session() as session:
            drops = list(
                await session.scalars(
                    select(WaifuGiftDrop)
                    .where(WaifuGiftDrop.status == "delivery_unknown")
                    .order_by(WaifuGiftDrop.id.asc())
                    .limit(20)
                )
            )

        if not drops:
            await message.answer("✅ No hay regalos de Sunna en estado de entrega desconocida.")
            return

        await message.answer(
            f"⚠️ <b>Entregas ambiguas de Sunna: {len(drops)}</b>\n"
            "Confirmá un envío solo después de comprobar manualmente el mensaje en Telegram. "
            "Reencolá solo cuando hayas comprobado que el mensaje no fue publicado."
        )
        for drop in drops:
            await message.answer(
                f"🎁 <b>Drop #{drop.id}</b>\n"
                f"Comunidad: <code>{drop.chat_id}</code>\n"
                f"Fecha: <b>{drop.day_key}</b> · slot: <b>{drop.slot}</b>\n"
                f"Objeto: <b>{self.gifts.gift_for_key(drop.gift_key).name}</b>",
                reply_markup=gift_delivery_recovery_keyboard(drop.id),
            )

    async def gift_delivery_recovery(self, callback: CallbackQuery) -> None:
        if not self._is_owner(callback):
            await callback.answer("No autorizado.", show_alert=True)
            return

        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[3].isdigit():
            await callback.answer("Recuperación inválida.", show_alert=True)
            return

        drop_id = int(parts[3])
        action = parts[2]
        async with self.database.session(write=True) as session:
            if action == "confirm":
                changed = await self.gifts.confirm_unknown_delivery(
                    session,
                    drop_id=drop_id,
                )
            elif action == "requeue":
                changed = await self.gifts.requeue_unknown_delivery(
                    session,
                    drop_id=drop_id,
                )
            else:
                await callback.answer("Acción inválida.", show_alert=True)
                return

        if not changed:
            await callback.answer(
                "El drop ya fue resuelto o no está disponible para esta acción.",
                show_alert=True,
            )
            return

        text = (
            f"Drop #{drop_id}: publicación confirmada ✅"
            if action == "confirm"
            else f"Drop #{drop_id}: reencolado 🔁"
        )
        if callback.message is not None:
            await callback.message.edit_text(text)
        await callback.answer("Estado guardado.")

    async def rare_decision(self, callback: CallbackQuery, bot: Bot) -> None:
        if not self._is_owner(callback):
            await callback.answer("No autorizado.", show_alert=True)
            return

        parts = (callback.data or "").split(":")
        if (
            len(parts) != 4
            or not parts[3].isdigit()
            or parts[2] not in {"approve", "reject"}
        ):
            await callback.answer("Solicitud inválida.", show_alert=True)
            return

        approval_id = int(parts[3])
        approved = parts[2] == "approve"

        async with self.database.session() as session:
            request = await decide(session, approval_id, approved, commit=False)
            if request is None:
                await callback.answer(
                    "Solicitud ya resuelta o inexistente.",
                    show_alert=True,
                )
                return

            _, balance = await self.gacha.finalize_approval(session, request)
            await session.commit()

        character = get_character(request.character_id)
        status = "APROBADA ✅" if approved else "RECHAZADA ❌"
        result_text = (
            f"Solicitud #{request.id}: {request.rarity} · {status} · "
            f"Saldo del jugador: {balance}"
        )
        if callback.message is not None:
            await callback.message.edit_text(result_text)

        await self._notify_player(
            bot,
            request.target_user_id,
            character.name,
            request.rarity,
            approved,
            balance,
        )
        await callback.answer("Decisión guardada.")

    async def _notify_player(
        self,
        bot: Bot,
        user_id: int,
        character_name: str,
        rarity: str,
        approved: bool,
        balance: int,
    ) -> None:
        """Best-effort private result; the persisted decision remains authoritative."""
        if approved:
            text = (
                "🌟 <b>¡Tu drop raro fue aprobado!</b>\n\n"
                f"🎭 {character_name}\n"
                f"✨ Rareza: <b>{rarity}</b>\n"
                f"💰 Saldo: <b>{balance}</b>\n\n"
                "Sunna ya dejó la recompensa en tu colección."
            )
        else:
            text = (
                "📝 <b>Tu drop raro fue rechazado.</b>\n\n"
                f"🎭 {character_name}\n"
                f"✨ Rareza solicitada: <b>{rarity}</b>\n"
                f"💰 Se devolvió el costo. Saldo: <b>{balance}</b>."
            )
        try:
            await bot.send_message(user_id, text)
        except TelegramAPIError:
            logger.info(
                "Could not deliver private gacha decision to user=%s approval_character=%s",
                user_id,
                character_name,
            )
