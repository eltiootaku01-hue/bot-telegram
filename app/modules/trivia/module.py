from __future__ import annotations

import asyncio
import random

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update

from app.core.module import BotModule
from app.db.database import Database
from app.db.models import Chat, GameProfile
from app.db.trivia_models import TriviaRound
from app.game.trivia import TriviaService
from app.ui.game_keyboards import trivia_keyboard


class TriviaModule(BotModule):
    """Anime trivia and points; public interaction is button-first."""

    name = "trivia"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.service = TriviaService()
        self._bot: Bot | None = None

    def setup(self) -> None:
        self.router.message.register(self.start_command, Command("trivia"))
        self.router.message.register(self.points_command, Command("puntos"))
        self.router.message.register(self.ranking_command, Command("ranking"))
        self.router.callback_query.register(self.answer, F.data.startswith("game:trivia:"))

    async def on_startup(self, bot: Bot) -> None:
        self._bot = bot
        self.tasks.start("trivia-scheduler", self._scheduler())

    async def start_command(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await message.answer("🧠 La trivia pública aparece sola. Acá podés consultar su estado.")

    async def _publish(self, chat_id: int, source: Message | None = None) -> bool:
        async with self.database.session() as session:
            created = await self.service.start_round(session, chat_id)
        if created is None:
            return False
        round_row, question = created
        text = f"🧠 <b>TRIVIA ANIME</b>\n\n{question.question}\n\n⏱️ 90 segundos · 🏆 +{question.points} puntos"
        try:
            if source is not None:
                await source.answer(text, reply_markup=trivia_keyboard(round_row.id, question.options))
            elif self._bot is not None:
                await self._bot.send_message(chat_id, text, reply_markup=trivia_keyboard(round_row.id, question.options))
            else:
                return False
        except Exception:
            async with self.database.session() as session:
                await session.execute(
                    update(TriviaRound).where(TriviaRound.id == round_row.id).values(status="failed")
                )
                await session.commit()
            return False
        return True

    async def answer(self, callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
            await callback.answer("Trivia inválida.", show_alert=True)
            return
        round_id, option_index = int(parts[2]), int(parts[3])
        async with self.database.session() as session:
            result, balance = await self.service.answer(session, round_id, callback.from_user.id, option_index)
            round_row = await session.get(TriviaRound, round_id)
        if round_row is None:
            await callback.answer("La trivia ya no existe.", show_alert=True)
            return
        if result == "correct":
            await callback.answer(f"¡Correcto! +{round_row.points} puntos", show_alert=True)
            if callback.message is not None:
                await callback.message.edit_text(
                    f"🎉 <b>{callback.from_user.first_name}</b> ganó la trivia.\n"
                    f"🏆 +{round_row.points} puntos · 💰 saldo: {balance}\n\n"
                    f"💡 {round_row.explanation}"
                )
            return
        if result == "wrong":
            await callback.answer("❌ Incorrecto. Probá suerte en la próxima.")
        elif result == "already_answered":
            await callback.answer("Ya respondiste esta trivia.")
        else:
            await callback.answer("La trivia ya terminó. 😭")

    async def points_command(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        async with self.database.session() as session:
            profile = await session.scalar(
                select(GameProfile).where(
                    GameProfile.user_id == message.from_user.id,
                    GameProfile.chat_id == message.chat.id,
                )
            )
        points = profile.points if profile is not None else 0
        await message.answer(f"💰 <b>{message.from_user.first_name}</b>: {points} puntos")

    async def ranking_command(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await message.answer("🏆 El ranking público se mostrará mediante el panel de puntos.")

    async def _scheduler(self) -> None:
        await asyncio.sleep(random.randint(60, 180))
        while True:
            try:
                async with self.database.session() as session:
                    chats = list(
                        await session.scalars(
                            select(Chat.id).where(Chat.type.in_(["group", "supergroup"]))
                        )
                    )
                if chats:
                    await self._publish(random.choice(chats))
            except Exception:
                pass
            await asyncio.sleep(random.randint(1200, 2400))
