from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MediaAsset


@dataclass(frozen=True, slots=True)
class MediaQueueSummary:
    inbox: int
    needs_tag: int
    waiting_schedule: int
    scheduled: int
    publishing: int
    delivery_unknown: int
    published: int
    oldest_actionable_at: datetime | None


class MediaLibrary:
    """Database-backed inbox and identity index for Telegram media.

    Telegram file_id is the reusable transport handle. file_unique_id is
    the stable identity signal used to detect reposts without downloading the
    file again. Metadata remains local so assets can later be reused by
    publishers, games and future web/admin surfaces.
    """

    ACTIONABLE_STATUSES = (
        "cami_inbox",
        "needs_tag",
        "waiting_destination",
        "waiting_schedule",
        "scheduled",
        "publishing",
        "delivery_unknown",
    )

    async def get(self, session: AsyncSession, asset_id: int) -> MediaAsset | None:
        return await session.get(MediaAsset, asset_id)

    async def find_by_file_id(
        self,
        session: AsyncSession,
        telegram_file_id: str,
    ) -> MediaAsset | None:
        return await session.scalar(
            select(MediaAsset).where(MediaAsset.telegram_file_id == telegram_file_id)
        )

    async def find_by_unique_id(
        self,
        session: AsyncSession,
        telegram_unique_id: str | None,
    ) -> MediaAsset | None:
        if not telegram_unique_id:
            return None
        return await session.scalar(
            select(MediaAsset)
            .where(MediaAsset.telegram_unique_id == telegram_unique_id)
            .order_by(MediaAsset.id.asc())
            .limit(1)
        )

    async def find_existing(
        self,
        session: AsyncSession,
        *,
        telegram_file_id: str,
        telegram_unique_id: str | None,
        source_chat_id: int,
        source_message_id: int,
    ) -> MediaAsset | None:
        """Find the same Telegram media before creating a new catalog row.

        Matching order is intentionally transport-safe:
        exact file_id, then stable file_unique_id, then the exact source
        message. This covers retries and reposts while keeping the source
        location as a final fallback.
        """
        existing = await self.find_by_file_id(session, telegram_file_id)
        if existing is not None:
            return existing

        existing = await self.find_by_unique_id(session, telegram_unique_id)
        if existing is not None:
            return existing

        return await session.scalar(
            select(MediaAsset)
            .where(
                MediaAsset.source_chat_id == source_chat_id,
                MediaAsset.source_message_id == source_message_id,
            )
            .order_by(MediaAsset.id.asc())
            .limit(1)
        )

    async def update_metadata(
        self,
        session: AsyncSession,
        asset: MediaAsset,
        *,
        character_id: str | None = None,
        anime: str | None = None,
        tags: str | None = None,
        category: str | None = None,
        rarity: str | None = None,
        status: str | None = None,
        publish_group: bool | None = None,
        publish_page: bool | None = None,
        commit: bool = True,
    ) -> MediaAsset:
        if character_id is not None:
            asset.character_id = character_id
        if anime is not None:
            asset.anime = anime
        if tags is not None:
            asset.tags = tags
        if category is not None:
            asset.category = category
        if rarity is not None:
            asset.rarity = rarity
        if status is not None:
            asset.status = status
        if publish_group is not None:
            asset.publish_group = publish_group
        if publish_page is not None:
            asset.publish_page = publish_page
        await session.flush()
        if commit:
            await session.commit()
            await session.refresh(asset)
        return asset

    async def queue_summary(self, session: AsyncSession) -> MediaQueueSummary:
        counts = {}
        for status in (
            "cami_inbox",
            "needs_tag",
            "waiting_schedule",
            "scheduled",
            "publishing",
            "delivery_unknown",
            "published",
        ):
            counts[status] = int(
                await session.scalar(
                    select(func.count(MediaAsset.id)).where(MediaAsset.status == status)
                )
                or 0
            )
        oldest = await session.scalar(
            select(func.min(MediaAsset.updated_at)).where(
                MediaAsset.status.in_(self.ACTIONABLE_STATUSES)
            )
        )
        return MediaQueueSummary(
            inbox=counts["cami_inbox"],
            needs_tag=counts["needs_tag"],
            waiting_schedule=counts["waiting_schedule"],
            scheduled=counts["scheduled"],
            publishing=counts["publishing"],
            delivery_unknown=counts["delivery_unknown"],
            published=counts["published"],
            oldest_actionable_at=oldest,
        )

    async def pending(self, session: AsyncSession, limit: int = 50) -> list[MediaAsset]:
        result = await session.scalars(
            select(MediaAsset)
            .where(MediaAsset.status == "cami_inbox")
            .order_by(MediaAsset.created_at.asc())
            .limit(limit)
        )
        return list(result)
