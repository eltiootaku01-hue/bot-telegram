import asyncio
import logging
import random
from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import GameEncounter
from app.game.catalog import wild_characters
from app.services.telegram_delivery import with_retry_after
from app.game.encounters import encounter_options, new_encounter
from app.ui.game_keyboards import encounter_keyboard

logger = logging.getLogger(__name__)


class WildWaifuScheduler:
    """Creates occasional public encounters only in the configured community."""

    def __init__(
        self,
        bot: Bot,
        database: Database,
        settings: Settings | None = None,
    ) -> None:
        self.bot = bot
        self.database = database
        self.settings = settings or get_settings()
        self.task: asyncio.Task | None = None
        self.spawn_tasks: set[asyncio.Task] = set()
        self.stopping = False

    def start(self) -> None:
        if self.task is None or self.task.done():
            self.stopping = False
            self.task = asyncio.create_task(self._run(), name="wild-waifu-scheduler")

    async def stop(self) -> None:
        self.stopping = True
        tasks = list(self.spawn_tasks)
        if self.task is not None:
            self.task.cancel()
            tasks.append(self.task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.spawn_tasks.clear()
        self.task = None

    async def _run(self) -> None:
        while not self.stopping:
            try:
                await asyncio.sleep(random.randint(60, 600))
                for chat_id in await self._group_ids():
                    if self.stopping:
                        break
                    task = asyncio.create_task(self.spawn(chat_id), name=f"waifu-spawn-{chat_id}")
                    self.spawn_tasks.add(task)
                    task.add_done_callback(self._spawn_done)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Wild waifu scheduler cycle failed")

    def _spawn_done(self, task: asyncio.Task) -> None:
        self.spawn_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            logger.exception("Wild waifu spawn task failed")

    async def _group_ids(self) -> list[int]:
        """Only the currently configured Chie community may receive wild encounters."""
        async with self.database.session() as session:
            result = await session.scalars(
                select(SetupSession.chat_id)
                .where(
                    SetupSession.bot_identity == "chie",
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
            )
            return [
                chat_id
                for chat_id in dict.fromkeys(result)
                if is_authorized_community(self.settings, chat_id)
            ]

    async def _has_active_encounter(self, chat_id: int) -> bool:
        now = utc_now()
        async with self.database.session() as session:
            await session.execute(
                update(GameEncounter)
                .where(
                    GameEncounter.chat_id == chat_id,
                    GameEncounter.status == "active",
                    GameEncounter.expires_at <= now,
                )
                .values(status="expired")
            )
            encounter = await session.scalar(
                select(GameEncounter.id)
                .where(
                    GameEncounter.chat_id == chat_id,
                    GameEncounter.status == "active",
                    GameEncounter.expires_at > now,
                )
                .limit(1)
            )
            return encounter is not None

    async def spawn(self, chat_id: int) -> None:
        # Background sends must honor the same central allowlist as inbound updates.
        if not is_authorized_community(self.settings, chat_id):
            return

        # The database is the source of truth, so a restart or duplicate scheduler
        # cannot flood a chat with multiple active encounters.
        if await self._has_active_encounter(chat_id):
            return

        characters = wild_characters()
        if not characters:
            return
        character = random.choice(characters)
        encounter = new_encounter(character)
        expires = encounter.expires_at
        options = encounter_options(encounter)
        if encounter.question:
            text = (
                "🚨 <b>¡WAIFU SUELTA!</b> 🚨\n\n"
                f"👤 <b>{character.name}</b> · clase {character.rarity.value}\n"
                f"❓ {encounter.question}\n👥 Hasta 3 personas pueden intentarlo. Una oportunidad por persona."
            )
        else:
            text = (
                "🚨 <b>¡WAIFU SUELTA!</b> 🚨\n\n"
                f"👤 <b>{character.name}</b> · clase {character.rarity.value}\n"
                "⚡ ¡Elegí su nombre antes de que desaparezca!\n👥 Hasta 3 personas pueden intentarlo. Una oportunidad por persona."
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
        async with self.database.session() as session:
            session.add(record)
            try:
                await session.commit()
            except IntegrityError:
                # A second Sunna process may have raced us. The partial unique index
                # on active encounters makes only one winner possible.
                await session.rollback()
                return

        if not is_authorized_community(self.settings, chat_id):
            async with self.database.session() as session:
                await session.execute(
                    update(GameEncounter)
                    .where(
                        GameEncounter.id == encounter.id,
                        GameEncounter.status == "active",
                    )
                    .values(status="cancelled")
                )
            return

        try:
            sent = await with_retry_after(
                lambda: self.bot.send_message(
                    chat_id,
                    text,
                    reply_markup=encounter_keyboard(encounter.id, options),
                )
            )
        except Exception:
            logger.exception("Failed to publish encounter %s in chat %s", encounter.id, chat_id)
            async with self.database.session() as session:
                saved = await session.get(GameEncounter, encounter.id)
                if saved is not None:
                    saved.status = "cancelled"
                    await session.commit()
            return

        try:
            async with self.database.session() as session:
                saved = await session.get(GameEncounter, encounter.id)
                if saved is not None:
                    saved.message_id = sent.message_id
                    await session.commit()
        except Exception:
            logger.exception(
                "Could not persist Telegram message id for encounter %s",
                encounter.id,
            )

        await asyncio.sleep(max(0, (expires - utc_now()).total_seconds()))
        await self.expire(encounter.id, chat_id, sent.message_id)

    async def expire(self, encounter_id: str, chat_id: int, message_id: int) -> None:
        now = utc_now()
        async with self.database.session() as session:
            result = await session.execute(
                update(GameEncounter)
                .where(
                    GameEncounter.id == encounter_id,
                    GameEncounter.status == "active",
                    GameEncounter.expires_at <= now,
                )
                .values(status="expired")
            )
            if result.rowcount != 1:
                return
            await session.commit()
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="😭 La waifu se fue",
                reply_markup=None,
            )
        except Exception:
            logger.debug("Could not edit expired encounter %s", encounter_id, exc_info=True)
