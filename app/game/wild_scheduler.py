import asyncio
import random
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from app.db.database import Database
from app.db.models import Chat, GameEncounter
from app.game.catalog import CHARACTERS
from app.game.encounters import new_encounter
from app.ui.game_keyboards import encounter_keyboard


class WildWaifuScheduler:
    """Creates occasional group encounters and expires them without exposing answers."""

    def __init__(self, bot: Bot, database: Database) -> None:
        self.bot = bot
        self.database = database
        self.task: asyncio.Task | None = None
        self.expiry_tasks: set[asyncio.Task] = set()
        self.stopping = False

    def start(self) -> None:
        if self.task is None:
            self.stopping = False
            self.task = asyncio.create_task(self._run(), name="wild-waifu-scheduler")

    async def stop(self) -> None:
        self.stopping = True
        tasks = [task for task in self.expiry_tasks]
        if self.task is not None:
            self.task.cancel()
            tasks.append(self.task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.expiry_tasks.clear()
        self.task = None

    async def _run(self) -> None:
        while not self.stopping:
            await asyncio.sleep(random.randint(60, 600))
            chats = await self._group_ids()
            for chat_id in chats:
                task = asyncio.create_task(self.spawn(chat_id), name=f"waifu-{chat_id}")
                self.expiry_tasks.add(task)
                task.add_done_callback(self.expiry_tasks.discard)

    async def _group_ids(self) -> list[int]:
        async with self.database.sessions() as session:
            result = await session.scalars(
                select(Chat.id).where(Chat.type.in_(["group", "supergroup"]))
            )
            return list(result)

    async def spawn(self, chat_id: int) -> None:
        # Wild encounters currently cap at class B: rare characters or below.
        character = random.choice(list(CHARACTERS.values()))
        encounter = new_encounter(character)
        expires = encounter.expires_at
        question = encounter.question
        if question:
            options = ["Ryuuji", "Kitamura", "Ami"]
            text = (
                "🚨 <b>¡WAIFU SUELTA!</b> 🚨\n\n"
                f"👤 <b>{character.name}</b> · clase B\n"
                "🧠 <b>Pregunta de nicho:</b> ¿Cómo se llama el protagonista masculino de Toradora!?\n"
                "⚠️ Solo tenés <b>una oportunidad</b>."
            )
        else:
            options = ["🏃 Capturar"]
            text = (
                "🚨 <b>¡WAIFU SUELTA!</b> 🚨\n\n"
                f"👤 <b>{character.name}</b> · clase C\n"
                "⚡ ¡Capturala antes de que desaparezca!"
            )

        record = GameEncounter(
            id=encounter.id,
            chat_id=chat_id,
            character_id=character.id,
            rarity="B" if question else "C",
            question=question,
            answer="ryuuji" if question else None,
            expires_at=expires,
        )
        async with self.database.sessions() as session:
            session.add(record)
            await session.commit()

        sent = await self.bot.send_message(
            chat_id,
            text,
            reply_markup=encounter_keyboard(encounter.id, options),
        )
        async with self.database.sessions() as session:
            saved = await session.get(GameEncounter, encounter.id)
            if saved is not None:
                saved.message_id = sent.message_id
                await session.commit()

        await asyncio.sleep(max(0, (expires - datetime.utcnow()).total_seconds()))
        await self.expire(encounter.id, chat_id, sent.message_id)

    async def expire(self, encounter_id: str, chat_id: int, message_id: int) -> None:
        async with self.database.sessions() as session:
            encounter = await session.get(GameEncounter, encounter_id)
            if encounter is None or encounter.status != "active":
                return
            encounter.status = "expired"
            await session.commit()
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="😭 La waifu se fue 😭",
            )
        except Exception:
            return
