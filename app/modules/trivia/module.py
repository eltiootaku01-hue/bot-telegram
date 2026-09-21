from __future__ import annotations

import asyncio
import logging
import random
from html import escape

from aiogram import Bot, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.time import utc_now
from app.services.community import CommunityResolver
from app.services.world import WorldService
from app.db.database import Database
from app.db.models import GameProfile, User
from app.db.trivia_models import TriviaRound
from app.game.missions import DailyMissionService
from app.game.trivia import TriviaService
from app.ui.game_keyboards import trivia_keyboard
from app.services.telegram_delivery import with_retry_after

logger = logging.getLogger(__name__)


class TriviaModule(BotModule):
    """Anime trivia and points; public interaction is button-first."""

    name = "trivia"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.service = TriviaService()
        self.missions = DailyMissionService()
        self._bot: Bot | None = None
        self.world = WorldService()
        self.community = CommunityResolver(self.settings)

    def setup(self) -> None:
        self.router.message.register(self.start_command, Command("trivia"))
        self.router.message.register(self.points_command, Command("puntos"))
        self.router.message.register(self.ranking_command, Command("ranking"))
        self.router.callback_query.register(self.open_callback, F.data == "cafe:trivia:open")
        self.router.callback_query.register(self.start_panel, F.data == "game:trivia:start")
        self.router.callback_query.register(self.answer, F.data.startswith("game:trivia:"))

    async def on_startup(self, bot: Bot) -> None:
        self._bot = bot
        self.tasks.start("trivia-scheduler", self._scheduler())

    async def start_panel(self, callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer("No pude abrir la trivia.", show_alert=True)
            return
        chat = getattr(callback.message, "chat", None)
        if chat is not None and chat.type in {"group", "supergroup"}:
            await callback.answer("La consulta de trivia se hace desde tu chat privado con Cari.", show_alert=True)
            return
        community_chat_id = await self._community_chat_id(callback.from_user.id)
        if community_chat_id is None:
            await callback.answer("Chie todavía no configuró la comunidad.", show_alert=True)
            return

        async with self.database.session() as session:
            active = await session.scalar(
                select(TriviaRound).where(
                    TriviaRound.chat_id == community_chat_id,
                    TriviaRound.status == "active",
                    TriviaRound.expires_at > utc_now(),
                )
            )
        if active is None:
            await callback.message.edit_text(
                "🧠 <b>Trivia de Cari</b>\n\n"
                "No hay una trivia activa ahora. Las rondas aparecen automáticamente "
                "en la comunidad configurada."
            )
        else:
            await callback.message.edit_text(
                "🧠 <b>Trivia activa — Cari</b>\n\n"
                f"{escape(active.question)}\n\n"
                f"🏆 +{active.points} puntos\n"
                "Respondé desde los botones de la ronda pública."
            )
        await callback.answer()

    async def start_callback(self, callback: CallbackQuery) -> None:
        """Backward-compatible alias for the Cari trivia status panel."""
        await self.start_panel(callback)
    async def start_command(self, message: Message) -> None:
        if message.chat.type in {"group", "supergroup"}:
            if await self._publish(message.chat.id, source=message):
                return
            await message.answer("🧠 Ya hay una trivia activa en esta comunidad.")
            return
        await message.answer("🧠 La Trivia de Cari se juega en la comunidad. Desde acá podés consultar el estado.")

    async def open_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer("No pude abrir la trivia.", show_alert=True)
            return
        if not is_authorized_community(self.settings, callback.message.chat.id):
            await callback.answer("Esta comunidad no está autorizada.", show_alert=True)
            return
        published = await self._publish(callback.message.chat.id, source=callback.message)
        await callback.answer("Trivia lista." if published else "Ya hay una trivia activa.")

    async def _publish(self, chat_id: int, source: Message | None = None) -> bool:
        if not is_authorized_community(self.settings, chat_id):
            return False

        async with self.database.session(write=True) as session:
            created = await self.service.start_round(session, chat_id)
            if created is None:
                return False
            round_row, question = created
            claimed = await session.execute(
                update(TriviaRound)
                .where(
                    TriviaRound.id == round_row.id,
                    TriviaRound.status == "active",
                    TriviaRound.message_id.is_(None),
                )
                .values(status="publishing")
            )
            if claimed.rowcount != 1:
                return False
        text = f"🧠 <b>TRIVIA ANIME</b>\n\n{question.question}\n\n⏱️ 90 segundos · 🏆 +{question.points} puntos"
        if not is_authorized_community(self.settings, chat_id):
            async with self.database.session() as session:
                await session.execute(
                    update(TriviaRound)
                    .where(TriviaRound.id == round_row.id, TriviaRound.status == "active")
                    .values(status="cancelled")
                )
            return False
        try:
            if source is not None:
                sent = await source.answer(
                    text,
                    reply_markup=trivia_keyboard(round_row.id, question.options),
                )
            elif self._bot is not None:
                sent = await with_retry_after(
                    lambda: self._bot.send_message(
                        chat_id,
                        text,
                        reply_markup=trivia_keyboard(round_row.id, question.options),
                    )
                )
            else:
                raise RuntimeError("Cari trivia bot is not initialized")
        except Exception as exc:
            logger.exception("Trivia publication failed chat=%s round=%s", chat_id, round_row.id)
            async with self.database.session(write=True) as session:
                if isinstance(exc, RuntimeError):
                    await session.execute(
                        update(TriviaRound)
                        .where(TriviaRound.id == round_row.id, TriviaRound.status == "publishing")
                        .values(status="failed")
                    )
                else:
                    await session.execute(
                        update(TriviaRound)
                        .where(TriviaRound.id == round_row.id, TriviaRound.status == "publishing")
                        .values(status="delivery_unknown")
                    )
            return False

        async with self.database.session(write=True) as session:
            updated = await session.execute(
                update(TriviaRound)
                .where(
                    TriviaRound.id == round_row.id,
                    TriviaRound.status == "publishing",
                    TriviaRound.message_id.is_(None),
                )
                .values(status="active", message_id=sent.message_id)
            )
            if updated.rowcount != 1:
                return False
        try:
            if source is not None and source.from_user is not None:
                async with self.database.session() as session:
                    await self.world.observe_action(
                        session,
                        bot_identity=BotIdentity.CARI,
                        action_key="trivia_publish",
                        user_id=source.from_user.id,
                        chat_id=chat_id,
                    )
        except Exception:
            logger.exception("World observation failed for Cari trivia publish")
        return True

    async def answer(self, callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) == 3 and parts[2] == "start":
            await callback.answer("La trivia aparece automáticamente en la comunidad configurada. 🧠", show_alert=True)
            return
        if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit() or callback.message is None:
            await callback.answer("Trivia inválida.", show_alert=True)
            return
        round_id, option_index = int(parts[2]), int(parts[3])
        async with self.database.session(write=True) as session:
            result, balance = await self.service.answer(
                session,
                round_id,
                callback.from_user.id,
                option_index,
                chat_id=callback.message.chat.id,
            )
            round_row = await session.get(TriviaRound, round_id)
            mission_claimed = False
            mission_balance = balance
            if result in {"correct", "wrong"}:
                day_key = self.missions.day_key(
                    timezone_name=self.settings.bot_world_timezone,
                )
                await self.missions.record(
                    session,
                    user_id=callback.from_user.id,
                    chat_id=callback.message.chat.id,
                    day_key=day_key,
                    mission_key="trivia_participation",
                    reference_type="trivia_answer",
                    reference_id=f"{round_id}:{callback.from_user.id}",
                )
                mission_claimed, mission_balance = await self.missions.claim(
                    session,
                    user_id=callback.from_user.id,
                    chat_id=callback.message.chat.id,
                    day_key=day_key,
                    mission_key="trivia_participation",
                )
                if mission_claimed:
                    balance = mission_balance
        if round_row is None:
            await callback.answer("La trivia ya no existe.", show_alert=True)
            return
        if result == "correct":
            await self._observe_action("trivia_correct", callback.from_user.id, callback.message.chat.id)
            await callback.answer(f"¡Correcto! +{round_row.points} puntos", show_alert=True)
            await callback.message.edit_text(
                f"🎉 <b>{callback.from_user.first_name}</b> ganó la trivia.\n"
                f"🏆 +{round_row.points} puntos · 💰 saldo: {balance}\n\n"
                f"💡 {round_row.explanation}"
            )
            return
        if result == "wrong":
            await self._observe_action("trivia_wrong", callback.from_user.id, callback.message.chat.id)
            await callback.answer("❌ Incorrecto. Probá suerte en la próxima.")
        elif result == "already_answered":
            await callback.answer("Ya respondiste esta trivia.")
        elif result == "wrong_chat":
            await callback.answer("Esta trivia pertenece a otra comunidad. 😰", show_alert=True)
        elif result == "invalid":
            await callback.answer("Respuesta inválida.", show_alert=True)
        else:
            await callback.answer("La trivia ya terminó. 😭")

    async def _observe_action(
        self,
        action_key: str,
        user_id: int,
        chat_id: int | None = None,
    ) -> None:
        """Record trivia usage outside the gameplay transaction."""
        try:
            async with self.database.session() as session:
                await self.world.observe_action(
                    session,
                    bot_identity=BotIdentity.CARI,
                    action_key=action_key,
                    user_id=user_id,
                    chat_id=chat_id,
                )
        except Exception:
            logger.exception("World observation failed for Trivia action=%s user=%s", action_key, user_id)
    async def _community_chat_id(self, user_id: int) -> int | None:
        async with self.database.session() as session:
            return await self.community.for_user(session, user_id)

    async def points_command(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        community_chat_id = await self._community_chat_id(message.from_user.id)
        if community_chat_id is None:
            await message.answer("😰 Chie todavía no configuró la comunidad.")
            return
        async with self.database.session() as session:
            profile = await session.scalar(
                select(GameProfile).where(
                    GameProfile.user_id == message.from_user.id,
                    GameProfile.chat_id == community_chat_id,
                )
            )
        points = profile.points if profile is not None else 0
        await message.answer(f"💰 <b>{message.from_user.first_name}</b>: {points} puntos")

    async def ranking_command(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        community_chat_id = await self._community_chat_id(message.from_user.id)
        if community_chat_id is None:
            await message.answer("😰 Chie todavía no configuró la comunidad.")
            return

        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(GameProfile, User)
                    .join(User, User.id == GameProfile.user_id)
                    .where(GameProfile.chat_id == community_chat_id)
                    .order_by(
                        GameProfile.points.desc(),
                        GameProfile.experience.desc(),
                        GameProfile.user_id.asc(),
                    )
                    .limit(10)
                )
            ).all()

        if not rows:
            await message.answer("🏆 Todavía no hay jugadores con perfil de puntos en la comunidad.")
            return

        lines = ["🏆 <b>Ranking de Ciudad Animals</b>", ""]
        medals = ("🥇", "🥈", "🥉")
        for position, (profile, user) in enumerate(rows, start=1):
            prefix = medals[position - 1] if position <= len(medals) else f"{position}."
            name = escape(user.first_name or user.username or f"Jugador {user.id}")
            lines.append(
                f"{prefix} <b>{name}</b> — {profile.points} puntos · Nv.{profile.level}"
            )
        await message.answer("\n".join(lines))
        await self._observe_action("ranking_view", message.from_user.id)

    async def _scheduler(self) -> None:
        await asyncio.sleep(random.randint(60, 180))
        while True:
            try:
                async with self.database.session() as session:
                    community_chat_ids = await self.community.configured(session)
                for community_chat_id in community_chat_ids:
                    if is_authorized_community(self.settings, community_chat_id):
                        await self._publish(community_chat_id)
            except Exception:
                logger.exception("Trivia scheduler tick failed")
            await asyncio.sleep(random.randint(1200, 2400))
