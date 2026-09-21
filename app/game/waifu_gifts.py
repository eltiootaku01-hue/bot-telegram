from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import (
    GameItemInventory,
    WaifuGiftClaim,
    WaifuGiftDrop,
)


MAX_GIFT_RECIPIENTS = 3


@dataclass(frozen=True, slots=True)
class WaifuGift:
    key: str
    name: str
    description: str
    experience: int


GIFTS: tuple[WaifuGift, ...] = (
    WaifuGift("fashion_magazine", "Revista de moda", "Inspiración para el vestuario", 30),
    WaifuGift("bread_slice", "Rodaja de pan", "Un snack sencillo para recuperar energía", 20),
    WaifuGift("dessert", "Postre del Café", "Un pequeño premio dulce", 40),
    WaifuGift("photo_card", "Fotocarta", "Una imagen coleccionable del Café", 25),
)


@dataclass(frozen=True, slots=True)
class GiftClaimResult:
    gift: WaifuGift
    quantity: int
    recipients_used: int


class WaifuGiftService:
    """Community gifts: three people may claim each drop, once per person."""

    @staticmethod
    def gift_for_key(key: str) -> WaifuGift:
        for gift in GIFTS:
            if gift.key == key:
                return gift
        raise KeyError(key)

    @classmethod
    def gift_for_slot(cls, chat_id: int, day_key: str, slot: int) -> WaifuGift:
        digest = hashlib.sha256(f"{chat_id}:{day_key}:{slot}".encode("utf-8")).digest()
        return GIFTS[int.from_bytes(digest[:8], "big") % len(GIFTS)]

    async def create_drop(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        day_key: str,
        slot: int,
        expires_at=None,
    ) -> WaifuGiftDrop:
        gift = self.gift_for_slot(chat_id, day_key, slot)
        row = await session.scalar(
            select(WaifuGiftDrop).where(
                WaifuGiftDrop.chat_id == chat_id,
                WaifuGiftDrop.day_key == day_key,
                WaifuGiftDrop.slot == slot,
            )
        )
        if row is not None:
            return row

        row = WaifuGiftDrop(
            chat_id=chat_id,
            day_key=day_key,
            slot=slot,
            gift_key=gift.key,
            status="pending",
            expires_at=expires_at or (utc_now() + timedelta(hours=6)),
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            row = await session.scalar(
                select(WaifuGiftDrop).where(
                    WaifuGiftDrop.chat_id == chat_id,
                    WaifuGiftDrop.day_key == day_key,
                    WaifuGiftDrop.slot == slot,
                )
            )
            if row is None:
                raise
        return row

    async def claim_publication(
        self,
        session: AsyncSession,
        *,
        drop_id: int,
    ) -> bool:
        result = await session.execute(
            update(WaifuGiftDrop)
            .where(
                WaifuGiftDrop.id == drop_id,
                WaifuGiftDrop.status.in_(("pending", "failed")),
                WaifuGiftDrop.message_id.is_(None),
            )
            .values(status="publishing", updated_at=utc_now())
        )
        return result.rowcount == 1

    async def mark_published(
        self,
        session: AsyncSession,
        *,
        drop_id: int,
        message_id: int,
    ) -> bool:
        result = await session.execute(
            update(WaifuGiftDrop)
            .where(
                WaifuGiftDrop.id == drop_id,
                WaifuGiftDrop.status == "publishing",
                WaifuGiftDrop.message_id.is_(None),
            )
            .values(status="active", message_id=message_id, updated_at=utc_now())
        )
        return result.rowcount == 1

    async def mark_publication_failed(
        self,
        session: AsyncSession,
        *,
        drop_id: int,
    ) -> None:
        await session.execute(
            update(WaifuGiftDrop)
            .where(
                WaifuGiftDrop.id == drop_id,
                WaifuGiftDrop.status == "publishing",
                WaifuGiftDrop.message_id.is_(None),
            )
            .values(status="pending", updated_at=utc_now())
        )

    async def claim(
        self,
        session: AsyncSession,
        *,
        drop_id: int,
        user_id: int,
        chat_id: int,
        profile_id: int,
    ) -> GiftClaimResult | None:
        drop = await session.get(WaifuGiftDrop, drop_id)
        if (
            drop is None
            or drop.chat_id != chat_id
            or drop.status != "active"
            or drop.expires_at <= utc_now()
        ):
            return None

        duplicate = await session.scalar(
            select(WaifuGiftClaim.id).where(
                WaifuGiftClaim.drop_id == drop_id,
                WaifuGiftClaim.user_id == user_id,
            )
        )
        if duplicate is not None:
            return None

        recipients = await session.scalar(
            select(func.count(WaifuGiftClaim.id)).where(
                WaifuGiftClaim.drop_id == drop_id,
            )
        )
        if (recipients or 0) >= MAX_GIFT_RECIPIENTS:
            return None

        claim = WaifuGiftClaim(
            drop_id=drop_id,
            user_id=user_id,
            chat_id=chat_id,
        )
        try:
            async with session.begin_nested():
                session.add(claim)
                await session.flush()
        except IntegrityError:
            return None

        gift = self.gift_for_key(drop.gift_key)
        inventory = await session.scalar(
            select(GameItemInventory).where(
                GameItemInventory.profile_id == profile_id,
                GameItemInventory.item_key == gift.key,
            )
        )
        if inventory is None:
            inventory = GameItemInventory(
                profile_id=profile_id,
                item_key=gift.key,
                quantity=1,
            )
            session.add(inventory)
        else:
            inventory.quantity += 1
        await session.flush()

        used = (recipients or 0) + 1
        return GiftClaimResult(
            gift=gift,
            quantity=inventory.quantity,
            recipients_used=used,
        )

    async def absorb(
        self,
        session: AsyncSession,
        *,
        profile_id: int,
        character_id: str,
        item_key: str,
    ) -> int | None:
        inventory = await session.scalar(
            select(GameItemInventory).where(
                GameItemInventory.profile_id == profile_id,
                GameItemInventory.item_key == item_key,
            )
        )
        if inventory is None or inventory.quantity <= 0:
            return None

        gift = self.gift_for_key(item_key)
        collection = await session.scalar(
            select(GameCollection).where(
                GameCollection.profile_id == profile_id,
                GameCollection.character_id == character_id,
            )
        )
        if collection is None:
            return None

        consumed = await session.execute(
            update(GameItemInventory)
            .where(
                GameItemInventory.id == inventory.id,
                GameItemInventory.quantity > 0,
            )
            .values(quantity=GameItemInventory.quantity - 1)
        )
        if consumed.rowcount != 1:
            return None

        from app.game.progression import add_character_experience

        progress = add_character_experience(
            level=collection.level,
            experience=collection.experience,
            evolution_stage=collection.evolution_stage,
            gained=gift.experience,
            copies=collection.copies,
        )
        collection.level = progress.level
        collection.experience = progress.experience
        await session.flush()
        return progress.level

    async def claim_count(
        self,
        session: AsyncSession,
        *,
        drop_id: int,
    ) -> int:
        return int(
            await session.scalar(
                select(func.count(WaifuGiftClaim.id)).where(
                    WaifuGiftClaim.drop_id == drop_id,
                )
            )
            or 0
        )
