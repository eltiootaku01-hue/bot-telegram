from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameCardCollection
from app.game.cards import WaifuCard, card_for_character, fusion_card_for_characters
from app.game.catalog import get_character


@dataclass(frozen=True, slots=True)
class CardGrantResult:
    card: WaifuCard
    copies: int


class CardCollectionService:
    """Persistent card inventory with atomic grants and UR fusion."""

    async def grant(
        self,
        session: AsyncSession,
        *,
        profile_id: int,
        card: WaifuCard,
    ) -> CardGrantResult:
        existing = await session.scalar(
            select(GameCardCollection).where(
                GameCardCollection.profile_id == profile_id,
                GameCardCollection.card_id == card.card_id,
            )
        )
        if existing is not None:
            updated = await session.execute(
                update(GameCardCollection)
                .where(
                    GameCardCollection.id == existing.id,
                    GameCardCollection.card_id == card.card_id,
                )
                .values(copies=GameCardCollection.copies + 1)
            )
            if updated.rowcount != 1:
                raise RuntimeError("Card grant changed during concurrent update")
            await session.flush()
            await session.refresh(existing)
            return CardGrantResult(card, existing.copies)

        row = GameCardCollection(
            profile_id=profile_id,
            card_id=card.card_id,
            character_id=card.character_id,
            card_tier=card.tier.value,
            variant=card.variant.value,
            outfit=card.outfit,
            fusion_of_a=card.fusion_of[0] if len(card.fusion_of) == 2 else None,
            fusion_of_b=card.fusion_of[1] if len(card.fusion_of) == 2 else None,
            copies=1,
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(GameCardCollection).where(
                    GameCardCollection.profile_id == profile_id,
                    GameCardCollection.card_id == card.card_id,
                )
            )
            if existing is None:
                raise
            await session.execute(
                update(GameCardCollection)
                .where(GameCardCollection.id == existing.id)
                .values(copies=GameCardCollection.copies + 1)
            )
            await session.flush()
            await session.refresh(existing)
            return CardGrantResult(card, existing.copies)
        return CardGrantResult(card, 1)

    async def fuse(
        self,
        session: AsyncSession,
        *,
        profile_id: int,
        first_collection_id: int,
        second_collection_id: int,
        seed: str,
        mature_art_allowed: bool = False,
    ) -> CardGrantResult:
        if first_collection_id == second_collection_id:
            raise ValueError("Una UR necesita dos cartas diferentes")

        rows = list(
            await session.scalars(
                select(GameCardCollection)
                .where(
                    GameCardCollection.profile_id == profile_id,
                    GameCardCollection.id.in_((first_collection_id, second_collection_id)),
                    GameCardCollection.copies > 0,
                )
            )
        )
        if len(rows) != 2:
            raise ValueError("Las dos cartas deben existir y tener copias disponibles")

        rows_by_id = {row.id: row for row in rows}
        first = rows_by_id[first_collection_id]
        second = rows_by_id[second_collection_id]
        if first.character_id.startswith("fusion:") or second.character_id.startswith("fusion:"):
            raise ValueError("Las UR no se pueden usar como base de otra UR")

        character_a = get_character(first.character_id)
        character_b = get_character(second.character_id)
        card = fusion_card_for_characters(
            character_a,
            character_b,
            seed=seed,
            mature_art_allowed=mature_art_allowed,
        )

        for row in sorted(rows, key=lambda item: item.id):
            claimed = await session.execute(
                update(GameCardCollection)
                .where(
                    GameCardCollection.id == row.id,
                    GameCardCollection.copies > 0,
                )
                .values(copies=GameCardCollection.copies - 1)
            )
            if claimed.rowcount != 1:
                raise ValueError("Una de las cartas ya no está disponible")

        result = await self.grant(session, profile_id=profile_id, card=card)
        await session.flush()
        return result


def card_for_gacha_character(
    character,
    *,
    seed: str,
    mature_art_allowed: bool = False,
) -> WaifuCard:
    """Build the exact collectible card represented by one gacha roll."""
    return card_for_character(
        character,
        seed=f"gacha:{seed}",
        mature_art_allowed=mature_art_allowed,
    )
