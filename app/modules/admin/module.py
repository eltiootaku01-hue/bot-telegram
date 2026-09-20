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
from app.db.models import RareDropApproval
from app.game.catalog import get_character
from app.game.gacha import GachaService
from app.game.rare_approval import decide
from app.ui.control_keyboards import rare_approval_keyboard

logger = logging.getLogger(__name__)


class AdminModule(BotModule):
    """Owner-only workflows for exceptional drops."""

    name = "admin"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.gacha = GachaService()

    def setup(self) -> None:
        self.router.message.register(
            self.pending_approvals_command,
            Command("gacha_pendientes"),
        )
        self.router.callback_query.register(
            self.rare_decision,
            F.data.startswith("admin:rare:"),
        )

    def _is_owner(self, callback: CallbackQuery) -> bool:
        return (
            bool(self.settings.admin_user_id)
            and callback.from_user.id == self.settings.admin_user_id
            and callback.message is not None
            and callback.message.chat.type == "private"
            and callback.message.chat.id == self.settings.admin_user_id
        )

    async def pending_approvals_command(self, message: Message) -> None:
        """Show pending rare-drop approvals so lost notifications remain recoverable."""
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.chat.id != self.settings.admin_user_id
            or message.from_user.id != self.settings.admin_user_id
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
