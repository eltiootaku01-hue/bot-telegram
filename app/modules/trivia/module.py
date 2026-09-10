from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update

from app.core.module import BotModule
from app.db.database import Database
from app.db.models import Chat
from app.db.trivia_models import TriviaRound
from app.game.trivia import TriviaService
from app.ui.game_keyboards import trivia_keyboard


class TriviaModule(BotModule):
    """Anime trivia as a second points source, independent from WaifuMon capture."""

    name = "trivia"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.service = TriviaService()

    def setup(self) -> None:
        self.router.message.register(self.start_command, Command("trivia"))
        self.router.callback_query.register(self.answer, F.data.startswith("game:trivia:"))

    async def on_startup(self, bot: Bot) -> None:
        self.tasks.start("trivia-scheduler", self._scheduler(bot))

    async def start_command(self, message: Message) -> None:
        if message.chat.type not in {"group", "supergroup"}:
            await message.answer("🧠 La trivia está pensada para los grupos.")
            return
        await self._publish(message.chat.id, message)

    async def _publish(self, chat_id: int, source: Message | None = None) -> bool:
        async with self.database.session() as session:
            created = await self.service.start_round(session, chat_id)
        if created is None:
            return False
        round_row, question = created
        target = source
        if target is not None:
            await target.answer(
                f"🧠 <b>TRIVIA ANIME</b>\n\n{question.question}\n\n"
                f"⏱️ 90 segundos · 🏆 +{question.points} puntos al primero que acierte",
                reply_markup=trivia_keyboard(round_row.id, question.options),
            )
            return True
        try:
            await self._bot.send_message(
                chat_id,
                f"🧠 <b>TRIVIA ANIME</b>\n\n{question.question}\n\n"
                f"⏱️ 90 segundos · 🏆 +{question.points} puntos al primero que acierte",
                reply_markup=trivia_keyboard(round_row.id, question.options),
            )
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
            result, balance = await self.service.answer(
                session, round_id, callback.from_user.id, option_index
            )
            round_row = await session.get(TriviaRound, round_id)
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
            await callback.answer("❌ Incorrecto. Podés volver a intentarlo en otra trivia.")
        elif result == "already_answered":
            await callback.answer("Ya respondiste esta trivia.")
        else:
            await callback.answer("La trivia ya terminó. 😭")

    async def _scheduler(self, bot: Bot) -> None:
        self._bot = bot
        await asyncio.sleep(random.randint(60, 180))
        while True:
            try:
                async with self.database.session() as session:
                    chats = list(await session.scalars(
                        select(Chat.id).where(Chat.type.in_(["group", "supergroup"]))
                    ))
                if chats:
                    chat_id = random.choice(chats)
                    await self._publish(chat_id)
            except Exception:
                pass
            await asyncio.sleep(random.randint(1200, 2400))
