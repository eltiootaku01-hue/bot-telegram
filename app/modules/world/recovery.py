from __future__ import annotations

from html import escape

from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.module import BotModule
from app.db.database import Database
from app.db.world_models import GameWorldEvent
from app.ui.control_keyboards import world_event_recovery_keyboard
from app.world.models import PresenterKind, WorldEventStatus, WorldPresenterRef
from app.world.service import WorldEventService


class WorldEventRecoveryModule(BotModule):
    """Private operator surface for resolving ambiguous world-event deliveries."""

    name = "world-recovery"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.events = WorldEventService()

    def setup(self) -> None:
        self.router.message.register(self.pending_command, Command("world_pendientes"))
        self.router.message.register(self.view_command, Command("world_ver"))
        self.router.message.register(self.confirm_command, Command("world_confirmar"))
        self.router.message.register(self.retry_command, Command("world_reintentar"))
        self.router.message.register(self.cancel_command, Command("world_cancelar"))
        self.router.callback_query.register(
            self.recovery_callback,
            F.data.startswith("world:recovery:"),
        )

    def _is_owner_private(self, message: Message) -> bool:
        return (
            message.chat.type == "private"
            and message.from_user is not None
            and self.settings.is_master(message.from_user.id)
            and message.chat.id == self.settings.master_user_id
        )

    async def pending_command(self, message: Message) -> None:
        if not self._is_owner_private(message):
            return

        async with self.database.session() as session:
            events = list(
                await session.scalars(
                    select(GameWorldEvent)
                    .where(GameWorldEvent.status == WorldEventStatus.DELIVERY_UNKNOWN.value)
                    .order_by(GameWorldEvent.id.asc())
                    .limit(20)
                )
            )

        if not events:
            await message.answer("✅ No hay eventos del mundo con entrega ambigua.")
            return

        await message.answer(
            f"⚠️ <b>{len(events)}</b> evento(s) del mundo requieren revisión."
        )
        for event in events:
            await message.answer(
                self._event_text(event),
                reply_markup=world_event_recovery_keyboard(event.id),
            )

    async def view_command(self, message: Message) -> None:
        if not self._is_owner_private(message) or not message.text:
            return
        event_id = self._parse_single_id(message.text, "/world_ver")
        if event_id is None:
            await message.answer("Uso: <code>/world_ver ID</code>")
            return
        async with self.database.session() as session:
            event = await session.get(GameWorldEvent, event_id)
        if event is None:
            await message.answer("Evento inexistente.")
            return
        await message.answer(
            self._event_text(event),
            reply_markup=(
                world_event_recovery_keyboard(event.id)
                if event.status == WorldEventStatus.DELIVERY_UNKNOWN.value
                else None
            ),
        )

    async def confirm_command(self, message: Message) -> None:
        if not self._is_owner_private(message) or not message.text:
            return
        parts = message.text.split()
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            await message.answer("Uso: <code>/world_confirmar ID MESSAGE_ID</code>")
            return
        async with self.database.session() as session:
            changed = await self.events.confirm_delivery_unknown(
                session,
                event_id=int(parts[1]),
                message_id=int(parts[2]),
            )
        await message.answer(
            "✅ Evento confirmado como publicado."
            if changed
            else "⚠️ No se confirmó: el evento ya fue resuelto o tiene un message_id."
        )

    async def retry_command(self, message: Message) -> None:
        if not self._is_owner_private(message) or not message.text:
            return
        parts = message.text.split()
        if len(parts) not in {2, 3} or not parts[1].isdigit():
            await message.answer(
                "Uso: <code>/world_reintentar ID [existing_bot:sunna]</code>"
            )
            return

        presenter = None
        if len(parts) == 3:
            try:
                kind_raw, key = parts[2].split(":", 1)
                presenter = WorldPresenterRef(
                    key=key,
                    kind=PresenterKind(kind_raw),
                )
            except (ValueError, TypeError):
                await message.answer(
                    "Presentador inválido. Ejemplo: <code>existing_bot:sunna</code>."
                )
                return

        async with self.database.session() as session:
            changed = await self.events.retry_delivery_unknown(
                session,
                event_id=int(parts[1]),
                presenter=presenter,
                reason=f"manual retry by master {self.settings.master_user_id}",
            )
        await message.answer(
            "🔁 Evento reencolado."
            if changed
            else "⚠️ No se reencoló: el evento ya fue resuelto o su entrega ya tiene message_id."
        )

    async def cancel_command(self, message: Message) -> None:
        if not self._is_owner_private(message) or not message.text:
            return
        event_id = self._parse_single_id(message.text, "/world_cancelar")
        if event_id is None:
            await message.answer("Uso: <code>/world_cancelar ID</code>")
            return

        async with self.database.session() as session:
            changed = await self.events.cancel_delivery_unknown(
                session,
                event_id=event_id,
                reason=f"manual cancellation by master {self.settings.master_user_id}",
            )
        await message.answer(
            "❌ Evento cancelado."
            if changed
            else "⚠️ El evento ya fue resuelto o cancelado."
        )

    async def recovery_callback(self, callback: CallbackQuery) -> None:
        if (
            callback.message is None
            or callback.from_user is None
            or not self._is_owner_private(callback.message)
            or callback.from_user.id != self.settings.master_user_id
        ):
            await callback.answer("No autorizado.", show_alert=True)
            return

        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[3].isdigit():
            await callback.answer("Evento inválido.", show_alert=True)
            return

        event_id = int(parts[3])
        action = parts[2]

        if action == "view":
            async with self.database.session() as session:
                event = await session.get(GameWorldEvent, event_id)
            if event is None:
                await callback.answer("Evento inexistente.", show_alert=True)
                return
            await callback.message.answer(self._event_text(event))
            await callback.answer("Mostrado.")
            return

        if action == "retry":
            async with self.database.session() as session:
                changed = await self.events.retry_delivery_unknown(
                    session,
                    event_id=event_id,
                    reason=f"manual retry by master {self.settings.master_user_id}",
                )
            await callback.answer(
                "Evento reencolado." if changed else "Evento ya resuelto.",
                show_alert=not changed,
            )
            return

        if action == "cancel":
            async with self.database.session() as session:
                changed = await self.events.cancel_delivery_unknown(
                    session,
                    event_id=event_id,
                    reason=f"manual cancellation by master {self.settings.master_user_id}",
                )
            await callback.answer(
                "Evento cancelado." if changed else "Evento ya resuelto.",
                show_alert=not changed,
            )
            return

        await callback.answer("Acción desconocida.", show_alert=True)

    @staticmethod
    def _parse_single_id(text: str, command: str) -> int | None:
        parts = text.split()
        if (
            len(parts) != 2
            or parts[0].split("@", 1)[0] != command
            or not parts[1].isdigit()
        ):
            return None
        return int(parts[1])

    @staticmethod
    def _event_text(event: GameWorldEvent) -> str:
        payload = event.payload_json
        if len(payload) > 1800:
            payload = payload[:1800] + "…"
        lines = [
            f"🌎 <b>Evento #{event.id}</b>",
            f"Tipo: <code>{escape(event.event_type)}</code>",
            f"Clave: <code>{escape(event.event_key)}</code>",
            f"Comunidad: <code>{event.chat_id}</code>",
            f"Presentador: <code>{escape(event.presenter_key)}</code>",
            f"Estado: <code>{escape(event.status)}</code>",
            f"Intentos: <code>{event.attempts}</code>",
            f"Programado: <code>{event.run_at.isoformat()}</code>",
            f"Creado: <code>{event.created_at.isoformat()}</code>",
            f"Actualizado: <code>{event.updated_at.isoformat()}</code>",
            f"Último error: <code>{escape(event.last_error or '-')}</code>",
            f"Título: <b>{escape(event.title)}</b>",
            f"<b>Payload:</b><code>{escape(payload)}</code>",
        ]
        return "\n".join(lines)
