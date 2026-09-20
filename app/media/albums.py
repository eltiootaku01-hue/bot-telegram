from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import MediaAlbum, MediaAsset


@dataclass(frozen=True, slots=True)
class MediaAlbumSummary:
    album_id: int
    media_group_id: str
    item_count: int
    status: str


class MediaAlbumService:
    """Durable Telegram album grouping for Cami's operator workflow."""

    async def get_or_create(
        self,
        session: AsyncSession,
        *,
        source_chat_id: int,
        media_group_id: str,
        owner_user_id: int,
    ) -> tuple[MediaAlbum, bool]:
        album = await session.scalar(
            select(MediaAlbum).where(
                MediaAlbum.source_chat_id == source_chat_id,
                MediaAlbum.media_group_id == media_group_id,
            )
        )
        if album is not None:
            return album, False

        album = MediaAlbum(
            source_chat_id=source_chat_id,
            media_group_id=media_group_id,
            owner_user_id=owner_user_id,
        )
        session.add(album)
        try:
            async with session.begin_nested():
                await session.flush()
        except IntegrityError:
            album = await session.scalar(
                select(MediaAlbum).where(
                    MediaAlbum.source_chat_id == source_chat_id,
                    MediaAlbum.media_group_id == media_group_id,
                )
            )
            if album is None:
                raise
            return album, False
        return album, True

    async def add_item(
        self,
        session: AsyncSession,
        album_id: int,
        *,
        asset_id: int,
    ) -> MediaAlbum | None:
        result = await session.execute(
            update(MediaAlbum)
            .where(MediaAlbum.id == album_id)
            .values(
                item_count=MediaAlbum.item_count + 1,
                updated_at=utc_now(),
            )
        )
        if result.rowcount != 1:
            return None
        return await session.get(MediaAlbum, album_id)

    async def claim_prompt(
        self,
        session: AsyncSession,
        album_id: int,
    ) -> bool:
        result = await session.execute(
            update(MediaAlbum)
            .where(
                MediaAlbum.id == album_id,
                MediaAlbum.prompted_at.is_(None),
            )
            .values(
                prompted_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        return result.rowcount == 1

    async def items(
        self,
        session: AsyncSession,
        *,
        source_chat_id: int,
        media_group_id: str,
    ) -> list[MediaAsset]:
        result = await session.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.source_chat_id == source_chat_id,
                MediaAsset.media_group_id == media_group_id,
            )
            .order_by(MediaAsset.source_message_id.asc(), MediaAsset.id.asc())
        )
        return list(result)

    async def summary(
        self,
        session: AsyncSession,
        album_id: int,
    ) -> MediaAlbumSummary | None:
        album = await session.get(MediaAlbum, album_id)
        if album is None:
            return None
        return MediaAlbumSummary(
            album_id=album.id,
            media_group_id=album.media_group_id,
            item_count=album.item_count,
            status=album.status,
        )

    async def mark_processing(
        self,
        session: AsyncSession,
        album_id: int,
    ) -> bool:
        result = await session.execute(
            update(MediaAlbum)
            .where(
                MediaAlbum.id == album_id,
                MediaAlbum.status == "open",
            )
            .values(status="processing", updated_at=utc_now())
        )
        return result.rowcount == 1

    async def mark_completed(
        self,
        session: AsyncSession,
        album_id: int,
    ) -> bool:
        result = await session.execute(
            update(MediaAlbum)
            .where(MediaAlbum.id == album_id, MediaAlbum.status == "processing")
            .values(status="completed", updated_at=utc_now())
        )
        return result.rowcount == 1
