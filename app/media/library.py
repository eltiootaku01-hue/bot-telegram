from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MediaAsset


class MediaLibrary:
    """Database-backed inbox for Telegram media.

    Telegram file IDs are the canonical payload reference; metadata stays local so
    assets can later be reused by the game, group publisher, page publisher and web UI.
    """

    async def get(self, session: AsyncSession, asset_id: int) -> MediaAsset | None:
        return await session.get(MediaAsset, asset_id)

    async def find_by_file_id(
        self, session: AsyncSession, telegram_file_id: str
    ) -> MediaAsset | None:
        return await session.scalar(
            select(MediaAsset).where(MediaAsset.telegram_file_id == telegram_file_id)
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
        await session.commit()
        await session.refresh(asset)
        return asset

    async def pending(self, session: AsyncSession, limit: int = 50) -> list[MediaAsset]:
        result = await session.scalars(
            select(MediaAsset)
            .where(MediaAsset.status == "inbox")
            .order_by(MediaAsset.created_at.asc())
            .limit(limit)
        )
        return list(result)
