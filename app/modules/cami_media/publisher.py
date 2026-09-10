from __future__ import annotations

from datetime import datetime
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select

from app.core.config import get_settings
from app.core.identity import BotIdentity
from app.core.jobs import JobQueue
from app.core.module import BotModule
from app.core.workers import DurableWorker
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import MediaAsset
from app.services.forum_topics import ForumTopicService


class CamiMediaPublisher(BotModule):
    """Durable publisher for Cami's scheduled media jobs."""

    name = "cami-media-publisher"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.jobs = JobQueue()
        self.topics = ForumTopicService(database)
        self.settings = get_settings()
        self.worker: DurableWorker | None = None

    def setup(self) -> None:
        pass

    async def on_startup(self, bot: Bot) -> None:
        worker = DurableWorker(self.database, job_queue=self.jobs)
        worker.register_job("media.publish", lambda payload: self.publish(bot, payload))
        self.worker = worker
        self.tasks.start("media-publish-worker", worker.run())

    async def on_shutdown(self) -> None:
        if self.worker is not None:
            self.worker.stop()
        await super().on_shutdown()

    async def publish(self, bot: Bot, payload: dict) -> None:
        asset_id = int(payload["asset_id"])
        destination = str(payload.get("destination", "both"))
        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            if asset is None or asset.status != "scheduled":
                return
            setup = await session.scalar(
                select(SetupSession)
                .where(
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
            )
            if setup is None:
                raise RuntimeError("No configured Chie community")
            group_id = setup.chat_id
            thread_id = await self.topics.get_thread_id(group_id, "noticias")
            if thread_id is None:
                raise RuntimeError("Configured community has no #noticias topic")
            file_id = asset.telegram_file_id
            caption = self._caption(asset)

        if destination not in {"both", "group"}:
            raise ValueError(f"Unsupported media destination: {destination}")

        try:
            await bot.send_photo(
                group_id,
                file_id,
                message_thread_id=thread_id,
                caption=caption,
            )
            if destination == "both" and self.settings.publish_page_chat_id:
                await bot.send_photo(self.settings.publish_page_chat_id, file_id, caption=caption)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            raise RuntimeError(f"Telegram rejected scheduled publication: {exc}") from exc

        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            if asset is not None and asset.status == "scheduled":
                asset.status = "published"
                asset.updated_at = datetime.utcnow()
                await session.commit()

    @staticmethod
    def _caption(asset: MediaAsset) -> str:
        parts = []
        if asset.character_id:
            parts.append(f"🎭 {escape(asset.character_id.replace('-', ' '))}")
        if asset.anime:
            parts.append(f"📺 {escape(asset.anime)}")
        if asset.tags:
            tags = " ".join(
                f"#{escape(tag.strip())}" for tag in asset.tags.split(",") if tag.strip()
            )
            parts.append(f"🏷️ {tags}")
        return "\n".join(parts) or "✨ Nuevo material de la comunidad"
