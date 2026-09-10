import asyncio
import random
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from app.db.database import Database
from app.db.models import Chat, GameEncounter
from app.game.catalog import wild_characters
from app.game.encounters import new_encounter
from app.ui.game_keyboards import encounter_keyboard


class WildWaifuScheduler:
    """Creates occasional public encounters, capped at classes D/C."""

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
        tasks = list(self.expiry_tasks)
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
            for chat_id in await self._group_ids():
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
        characters = wild_characters()
        if not characters:
            return
        character = random.choice(characters)
        encounter = new_encounter(character)
        expires = encounter.expires_at
        options = [character.name]
        text = (
            "🚨 <b>¡WAIFU SUELTA!</b> 🚨\n\n"
            f"👤 <b>{character.name}</b> · clase {character.rarity.value}\n"
            "⚡ ¡Elegí su nombre antes de que desaparezca!"
        )

        record = GameEncounter(
            id=encounter.id,
            chat_id=chat_id,
            character_id=character.id,
            rarity=character.rarity.value,
            question=encounter.question,
            answer=encounter.answer,
            expires_at=expires,
        )
        async with self.database.sessions() as session:
            session.add(record)
            await session.commit()

        sent = await self.bot.send_message(
            chat_id, text, reply_markup=encounter_keyboard(encounter.id, options)
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
                text="😭 La waifu se fue",
                reply_markup=None,
            )
        except Exception:
            pass
