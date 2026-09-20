from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select, update

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.time import world_now
from app.db.database import Database
from app.db.models import MysteryRound
from app.game.mystery import MysteryService
from app.services.forum_topics import ForumTopicService
from app.services.world import WorldService
from app.ui.game_keyboards import mystery_keyboard

logger = logging.getLogger(__name__)


class MysteryModule(BotModule):
    """Cami's deterministic daily investigation game for the community."""

    name = "mystery"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.service = MysteryService()
        self.topics = ForumTopicService(database)
        self.world = WorldService()
        self.bot: Bot | None = None

    def setup(self) -> None:
        self.router.message.register(self.start_command, Command("misterio"))
        self.router.callback_query.register(self.open_callback, F.data == "cami:mystery:open")
        self.router.callback_query.register(self.answer_callback, F.data.startswith("game:mystery:"))

    async def on_startup(self, bot: Bot) -> None:
        self.bot = bot
        self.tasks.start("mystery-daily", self._daily_loop())

    async def start_command(self, message: Message) -> None:
        if message.chat.type not in {"group", "supergroup"}:
            await message.answer("🕵️ El misterio de Cami se juega en la comunidad.")
            return
        await self.publish(message.chat.id, source=message)

    async def open_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer("No pude abrir el misterio.", show_alert=True)
            return
        if not is_authorized_community(self.settings, callback.message.chat.id):
            await callback.answer("Esta comunidad no está autorizada.", show_alert=True)
            return
        await self.publish(callback.message.chat.id, source=callback.message)
        await callback.answer()

    async def publish(self, chat_id: int, source: Message | None = None) -> bool:
        if not is_authorized_community(self.settings, chat_id):
            return False

        day_key = world_now(self.settings.bot_world_timezone).date().isoformat()
        async with self.database.session(write=True) as session:
            started = await self.service.start_round(
                session,
                chat_id=chat_id,
                day_key=day_key,
            )
            row = started.round
            if row.message_id is not None and row.status != "failed":
                return False
            if row.status == "failed":
                row.status = "active"
                row.winner_user_id = None
                row.message_id = None
                row.expires_at = datetime.utcnow() + timedelta(hours=24)

            claimed = await session.execute(
                update(MysteryRound)
                .where(
                    MysteryRound.id == row.id,
                    MysteryRound.status == "active",
                    MysteryRound.message_id.is_(None),
                )
                .values(status="publishing", updated_at=datetime.utcnow())
            )
            if claimed.rowcount != 1:
                return False
            await session.commit()
            await session.refresh(row)

        text = (
            f"🕵️ <b>Misterio de Cami — {started.case.title}</b>\n\n"
            f"{started.case.question}\n\n"
            "🔎 <b>Pistas:</b>\n"
            + "\n".join(f"• {clue}" for clue in started.case.clues)
            + "\n\nElegí una respuesta. Solo la primera persona correcta gana los puntos.\n"
            "Este caso es cotidiano y no modifica el canon."
        )

        try:
            thread_id = await self.topics.get_thread_id(chat_id, "trivia")
            if source is not None and source.chat.id == chat_id:
                sent = await source.answer(
                    text,
                    reply_markup=mystery_keyboard(row.id, started.case.options),
                )
            elif self.bot is not None:
                kwargs = {"message_thread_id": thread_id} if thread_id is not None else {}
                sent = await self.bot.send_message(
                    chat_id,
                    text,
                    reply_markup=mystery_keyboard(row.id, started.case.options),
                    **kwargs,
                )
            else:
                raise RuntimeError("Cami mystery bot is not initialized")
        except (TelegramBadRequest, TelegramForbiddenError, RuntimeError):
            async with self.database.session(write=True) as session:
                await session.execute(
                    update(MysteryRound)
                    .where(MysteryRound.id == row.id, MysteryRound.status == "publishing")
                    .values(status="failed", updated_at=datetime.utcnow())
                )
            logger.exception("Mystery publication failed: chat=%s round=%s", chat_id, row.id)
            return False

        async with self.database.session(write=True) as session:
            current = await session.get(MysteryRound, row.id)
            if current is None or current.status != "publishing":
                return False
            current.message_id = sent.message_id
            current.status = "active"
            current.updated_at = datetime.utcnow()
        await self._observe("mystery_publish", getattr(source.from_user, "id", 0) if source and source.from_user else 0, chat_id)
        return True

    async def answer_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None or not callback.data:
            await callback.answer("Misterio inválido.", show_alert=True)
            return
        if not is_authorized_community(self.settings, callback.message.chat.id):
            await callback.answer("Esta comunidad no está autorizada.", show_alert=True)
            return
        parts = callback.data.split(":")
        if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
            await callback.answer("Misterio inválido.", show_alert=True)
            return

        round_id = int(parts[2])
        option_index = int(parts[3])
        async with self.database.session(write=True) as session:
            result, balance = await self.service.answer(
                session,
                round_id=round_id,
                user_id=callback.from_user.id,
                option_index=option_index,
                chat_id=callback.message.chat.id,
            )
            row = await session.get(MysteryRound, round_id)

        if row is None:
            await callback.answer("Ese misterio ya no existe.", show_alert=True)
            return
        if result == "correct":
            await callback.answer(f"¡Correcto! +{row.points} puntos", show_alert=True)
            await callback.message.edit_text(
                f"✅ <b>{callback.from_user.first_name}</b> resolvió el misterio de Cami.\n"
                f"🏆 +{row.points} puntos · 💰 saldo: {balance}"
            )
            await self._observe("mystery_solve", callback.from_user.id, callback.message.chat.id)
            return
        if result == "wrong":
            await callback.answer("No. Revisá las pistas. 🔎")
        elif result == "already_answered":
            await callback.answer("Ya respondiste este misterio.")
        elif result == "already_won":
            await callback.answer("El misterio ya fue resuelto.")
        elif result == "invalid":
            await callback.answer("Respuesta inválida.", show_alert=True)
        else:
            await callback.answer("El misterio ya terminó. 😭")

    async def _daily_loop(self) -> None:
        while True:
            try:
                community_ids = await self._configured_communities()
                for chat_id in community_ids:
                    await self.publish(chat_id)
            except Exception:
                logger.exception("Mystery daily loop failed")
            await self.tasks_sleep()

    async def tasks_sleep(self) -> None:
        import asyncio
        await asyncio.sleep(3600)

    async def _configured_communities(self) -> list[int]:
        async with self.database.session() as session:
            rows = await session.scalars(
                select(MysteryRound.chat_id).where(MysteryRound.status == "active").distinct()
            )
            ids = {int(value) for value in rows}
        if self.settings.base_group_chat_id:
            ids.add(self.settings.base_group_chat_id)
        return [
            chat_id
            for chat_id in ids
            if is_authorized_community(self.settings, chat_id)
        ]

    async def _observe(self, action_key: str, user_id: int, chat_id: int | None = None) -> None:
        if user_id <= 0:
            return
        try:
            async with self.database.session() as session:
                await self.world.observe_action(
                    session,
                    bot_identity=BotIdentity.CAMI,
                    action_key=action_key,
                    user_id=user_id,
                    chat_id=chat_id,
                )
        except Exception:
            logger.exception("World observation failed for Cami mystery action=%s user=%s", action_key, user_id)
