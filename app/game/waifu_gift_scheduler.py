from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import select, update

from app.core.access import is_authorized_community
from app.core.config import Settings, get_settings
from app.core.time import utc_now, world_now
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import WaifuGiftDrop
from app.game.waifu_gifts import WaifuGiftService, GIFTS
from app.services.telegram_delivery import with_retry_after
from app.ui.game_keyboards import gift_keyboard

logger = logging.getLogger(__name__)

GIFT_SLOT_HOURS = 6


class WaifuGiftScheduler:
    """Publishes one community gift every six-hour world-time slot."""

    def __init__(
        self,
        bot: Bot,
        database: Database,
        settings: Settings | None = None,
    ) -> None:
        self.bot = bot
        self.database = database
        self.settings = settings or get_settings()
        self.service = WaifuGiftService()
        self.task: asyncio.Task | None = None
        self.stopping = False

    def start(self) -> None:
        if self.task is None or self.task.done():
            self.stopping = False
            self.task = asyncio.create_task(self._run(), name="waifu-gift-scheduler")

    async def stop(self) -> None:
        self.stopping = True
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        self.task = None

    async def _run(self) -> None:
        while not self.stopping:
            try:
                for chat_id in await self._group_ids():
                    await self.publish_current_slot(chat_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Waifu gift scheduler cycle failed")
            try:
                await asyncio.wait_for(asyncio.Event().wait(), timeout=300)
            except TimeoutError:
                pass

    async def _group_ids(self) -> list[int]:
        async with self.database.session() as session:
            rows = await session.scalars(
                select(SetupSession.chat_id).where(
                    SetupSession.bot_identity == "chie",
                    SetupSession.status == "configured",
                )
            )
            return [
                int(chat_id)
                for chat_id in dict.fromkeys(rows)
                if is_authorized_community(self.settings, int(chat_id))
            ]

    async def publish_current_slot(self, chat_id: int) -> None:
        if not is_authorized_community(self.settings, chat_id):
            return

        world = world_now(self.settings.bot_world_timezone)
        day_key = world.date().isoformat()
        slot = world.hour // GIFT_SLOT_HOURS

        async with self.database.session(write=True) as session:
            existing = await session.scalar(
                select(WaifuGiftDrop).where(
                    WaifuGiftDrop.chat_id == chat_id,
                    WaifuGiftDrop.day_key == day_key,
                    WaifuGiftDrop.slot == slot,
                )
            )
            if existing is None:
                drop = await self.service.create_drop(
                    session,
                    chat_id=chat_id,
                    day_key=day_key,
                    slot=slot,
                )
            else:
                drop = existing

            if drop.message_id is not None or drop.status == "active":
                return

            if not await self.service.claim_publication(session, drop_id=drop.id):
                return

        gift = self.service.gift_for_key(drop.gift_key)
        text = (
            "🎁 <b>REGALO DE SUNNA</b>\n\n"
            f"🍰 <b>{gift.name}</b>\n"
            f"{gift.description}.\n"
            f"✨ Al absorberlo otorga {gift.experience} EXP a una waifu.\n\n"
            "👥 Solo las primeras 3 personas pueden reclamar este regalo. "
            "Cada persona tiene una sola oportunidad."
        )
        try:
            sent = await with_retry_after(
                lambda: self.bot.send_message(
                    chat_id,
                    text,
                    reply_markup=gift_keyboard(drop.id),
                )
            )
        except Exception:
            async with self.database.session(write=True) as session:
                await self.service.mark_publication_failed(session, drop_id=drop.id)
            logger.exception("Failed to publish Sunna gift drop=%s chat=%s", drop.id, chat_id)
            return

        async with self.database.session(write=True) as session:
            saved = await session.get(WaifuGiftDrop, drop.id)
            if saved is None:
                return
            if saved.message_id is None and saved.status == "publishing":
                saved.message_id = sent.message_id
                saved.status = "active"
                await session.flush()
