from aiogram import F
from aiogram.types import CallbackQuery

from app.core.config import get_settings
from app.core.module import BotModule
from app.db.database import Database
from app.game.rare_approval import decide


class AdminModule(BotModule):
    """Only the owner can make the exceptional A/S/SS/SSS decision."""

    name = "admin"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.settings = get_settings()

    def setup(self) -> None:
        self.router.callback_query.register(self.rare_decision, F.data.startswith("admin:rare:"))

    def _is_owner(self, callback: CallbackQuery) -> bool:
        return bool(self.settings.admin_user_id) and callback.from_user.id == self.settings.admin_user_id

    async def rare_decision(self, callback: CallbackQuery) -> None:
        if not self._is_owner(callback):
            await callback.answer("No autorizado.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[3].isdigit() or parts[2] not in {"approve", "reject"}:
            await callback.answer("Solicitud inválida.", show_alert=True)
            return
        async with self.database.session() as session:
            request = await decide(session, int(parts[3]), parts[2] == "approve")
        if request is None:
            await callback.answer("Solicitud ya resuelta o inexistente.", show_alert=True)
            return
        if callback.message is not None:
            await callback.message.edit_text(
                f"Solicitud #{request.id}: {request.rarity} · "
                f"{'APROBADA' if request.status == 'approved' else 'RECHAZADA'}"
            )
        await callback.answer("Decisión guardada.")
