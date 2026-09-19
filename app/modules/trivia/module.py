from __future__ import annotations

import asyncio
import logging
import random
from html import escape

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity
from app.services.community import CommunityResolver
from app.services.world import WorldService
from app.core.module import BotModule
from app.core.time import utc_now
from app.db.database import Database
from app.db.models import GameProfile, User
from app.db.trivia_models import TriviaRound
from app.game.trivia import TriviaService
from app.ui.game_keyboards import trivia_keyboard

logger = logging.getLogger(__name__)


class TriviaModule(BotModule):
    """Anime trivia and points; public interaction is button-first."""

    name = "trivia"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.service = TriviaService()
        self._bot: Bot | None = None
        self.world = WorldService()
        self.community = CommunityResolver()

    def setup(self) -> None:
        self.router.message.register(self.start_command, Command("trivia"))
        self.router.message.register(self.points_command, Command("puntos"))
        self.router.message.register(self.ranking_command, Command("ranking"))
        self.router.callback_query.register(self.start_panel, F.data == "game:trivia:start")
        self.router.callback_query.register(self.answer, F.data.startswith("game:trivia:"))

    async def on_startup(self, bot: Bot) -> None:
        self._bot = bot
        self.tasks.start("trivia-scheduler", self._scheduler())

    async def start_command(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await message.answer("🧠 La trivia pública aparece sola. Acá podés consultar su estado.")

    async def start_panel(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.message.chat.type != "private":
            await callback.answer("La consulta de trivia se hace desde tu chat privado con Sunna.", show_alert=True)
            return
        community_chat_id = await self._community_chat_id(callback.from_user.id)
        if community_chat_id is None:
            await callback.answer("Todavía no hay una comunidad configurada.", show_alert=True)
            return
        async with self.database.session() as session:
            round_row = await session.scalar(
                select(TriviaRound)
                .where(
                    TriviaRound.chat_id == community_chat_id,
                    TriviaRound.status == "active",
                )
                .order_by(TriviaRound.id.desc())
            )
        if round_row is None or utc_now() >= round_row.expires_at:
            await callback.answer("No hay una trivia activa ahora. Aparecerá automáticamente en la comunidad.", show_alert=True)
            return
        await callback.message.edit_text(
            "🧠 <b>Trivia activa</b>\n\n"
            f"{round_row.question}\n\n"
            f"⏱️ Termina pronto · 🏆 +{round_row.points} puntos\n"
            "Respondé directamente en la publicación de trivia del grupo."
        )
        await self._observe_action("trivia_status", callback.from_user.id)
        await callback.answer()

    async def _publish(self, chat_id: int, source: Message | None = None) -> bool:
        if not is_authorized_community(self.settings, chat_id):
            return False

        async with self.database.session() as session:
            created = await self.service.start_round(session, chat_id)
        if created is None:
            return False
        round_row, question = created
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
                await source.answer(text, reply_markup=trivia_keyboard(round_row.id, question.options))
            elif self._bot is not None:
                await self._bot.send_message(chat_id, text, reply_markup=trivia_keyboard(round_row.id, question.options))
            else:
                return False
        except Exception:
            logger.exception("Failed to publish trivia round chat=%s round=%s", chat_id, round_row.id)
            async with self.database.session() as session:
                await session.execute(
                    update(TriviaRound).where(TriviaRound.id == round_row.id).values(status="failed")
                )
                await session.commit()
            return False
        return True

    async def answer(self, callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit() or callback.message is None:
            await callback.answer("Trivia inválida.", show_alert=True)
            return
        round_id, option_index = int(parts[2]), int(parts[3])
        async with self.database.session() as session:
            result, balance = await self.service.answer(
                session,
                round_id,
                callback.from_user.id,
                option_index,
                chat_id=callback.message.chat.id,
            )
            round_row = await session.get(TriviaRound, round_id)
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
                    bot_identity=BotIdentity.SUNNA,
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
        community_chat_id = await self._community_chat_id(callback.from_user.id)
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
        community_chat_id = await self._community_chat_id()
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
