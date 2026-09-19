from aiogram import F
from aiogram.types import CallbackQuery

from app.core.config import Settings, get_settings
from app.core.module import BotModule
from app.db.database import Database
from app.game.gacha import GachaService
from app.game.rare_approval import decide


class AdminModule(BotModule):
    """Owner-only workflows for exceptional drops."""

    name = "admin"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.gacha = GachaService()

    def setup(self) -> None:
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

    async def rare_decision(self, callback: CallbackQuery) -> None:
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

        status = "APROBADA ✅" if approved else "RECHAZADA ❌"
        result_text = (
            f"Solicitud #{request.id}: {request.rarity} · {status} · "
            f"Saldo del jugador: {balance}"
        )
        if callback.message is not None:
            await callback.message.edit_text(result_text)
        await callback.answer("Decisión guardada.")
