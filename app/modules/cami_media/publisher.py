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
from app.db.models import FanRequest, MediaAsset, RequestStatus, User
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
        worker.register_job("media.request_publish", lambda payload: self.publish_request(bot, payload))
        self.worker = worker
        self.tasks.start("media-publish-worker", worker.run())

    async def on_shutdown(self) -> None:
        if self.worker is not None:
            self.worker.stop()
        await super().on_shutdown()

    async def publish(self, bot: Bot, payload: dict) -> None:
        asset_id = int(payload["asset_id"])
        destination = str(payload.get("destination", "both"))
        if destination not in {"both", "group"}:
            raise ValueError(f"Unsupported media destination: {destination}")
        if destination == "both" and not self.settings.publish_page_chat_id:
            raise RuntimeError("Media destination 'both' requires PUBLISH_PAGE_CHAT_ID to be configured")

        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            if asset is None or asset.status != "scheduled":
                # 'publishing' is intentionally terminal for automatic retries: a
                # Telegram send can succeed immediately before a process crashes and
                # records its message_id. Retrying automatically would duplicate it.
                # A future reconciliation action can explicitly reset this state.
                return
            setup = await session.scalar(
                select(SetupSession)
                .where(SetupSession.bot_identity == BotIdentity.CHIE.value, SetupSession.status == "configured")
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
            group_message_id = asset.published_group_message_id
            page_message_id = asset.published_page_message_id

            # Fence the asset before any external Telegram side effect. If the
            # process dies after sendPhoto but before storing the message id, the
            # durable job may retry, but the asset will no longer be eligible for
            # automatic publication and can be reconciled instead of duplicated.
            asset.status = "publishing"
            asset.updated_at = datetime.utcnow()
            await session.commit()

        try:
            if group_message_id is None:
                sent = await bot.send_photo(group_id, file_id, message_thread_id=thread_id, caption=caption)
                async with self.database.session() as session:
                    current = await session.get(MediaAsset, asset_id)
                    if current is None:
                        return
                    if current.published_group_message_id is None:
                        current.published_group_message_id = sent.message_id
                        current.updated_at = datetime.utcnow()
                        await session.commit()

            if destination == "both" and page_message_id is None:
                sent = await bot.send_photo(self.settings.publish_page_chat_id, file_id, caption=caption)
                async with self.database.session() as session:
                    current = await session.get(MediaAsset, asset_id)
                    if current is None:
                        return
                    if current.published_page_message_id is None:
                        current.published_page_message_id = sent.message_id
                        current.updated_at = datetime.utcnow()
                        await session.commit()
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            raise RuntimeError(f"Telegram rejected scheduled publication: {exc}") from exc

        async with self.database.session() as session:
            current = await session.get(MediaAsset, asset_id)
            if current is None or current.status != "publishing":
                return
            group_done = current.published_group_message_id is not None
            page_done = destination != "both" or current.published_page_message_id is not None
            if group_done and page_done:
                current.status = "published"
                current.updated_at = datetime.utcnow()
                await session.commit()

    async def publish_request(self, bot: Bot, payload: dict) -> None:
        asset_id = int(payload["asset_id"])
        request_id = int(payload["request_id"])
        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            request = await session.get(FanRequest, request_id)
            if asset is None or request is None or asset.request_id != request_id:
                return
            if asset.published_request_message_id is not None:
                if request.status == RequestStatus.PROCESSING.value:
                    request.status = RequestStatus.COMPLETED.value
                asset.status = "published_request"
                request.updated_at = datetime.utcnow()
                asset.updated_at = datetime.utcnow()
                await session.commit()
                return
            if request.status != RequestStatus.PROCESSING.value or asset.status == "publishing_request":
                return

            setup = await session.scalar(
                select(SetupSession)
                .where(SetupSession.bot_identity == BotIdentity.CHIE.value, SetupSession.status == "configured")
                .order_by(SetupSession.id.desc())
            )
            if setup is None:
                raise RuntimeError("No configured Chie community")
            thread_id = await self.topics.get_thread_id(setup.chat_id, "pedidos")
            if thread_id is None:
                raise RuntimeError("Configured community has no #pedidos topic")
            request_user = await session.get(User, request.user_id)
            user_name = escape((request_user.first_name if request_user else "integrante") or "integrante")
            user_tag = f'<a href="tg://user?id={request.user_id}">{user_name}</a>'
            file_id = asset.telegram_file_id
            description = request.description
            group_id = setup.chat_id
            asset.status = "publishing_request"
            asset.updated_at = datetime.utcnow()
            await session.commit()

        try:
            sent = await bot.send_photo(
                group_id,
                file_id,
                message_thread_id=thread_id,
                caption=(f"🎨 <b>Pedido #{request_id} completado</b>\n👤 {user_tag}\n📝 {escape(description)}"),
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            raise RuntimeError(f"Telegram rejected request publication: {exc}") from exc

        async with self.database.session() as session:
            asset = await session.get(MediaAsset, asset_id)
            request = await session.get(FanRequest, request_id)
            if asset is None or request is None:
                return
            if asset.published_request_message_id is None:
                asset.published_request_message_id = sent.message_id
            if request.status == RequestStatus.PROCESSING.value:
                request.status = RequestStatus.COMPLETED.value
            if asset.request_id == request_id:
                asset.status = "published_request"
            request.updated_at = datetime.utcnow()
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
            tags = " ".join(f"#{escape(tag.strip())}" for tag in asset.tags.split(",") if tag.strip())
            parts.append(f"🏷️ {tags}")
        return "\n".join(parts) or "✨ Nuevo material de la comunidad"
