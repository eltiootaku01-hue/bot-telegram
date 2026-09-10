from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameCollection
from app.game.evolution import consume_for_fusion


@dataclass(frozen=True, slots=True)
class FusionResult:
    character_id: str
    from_rarity: str
    to_rarity: str
    consumed: int
    remaining: int


async def fuse_collection(session: AsyncSession, *, profile_id: int, character_id: str) -> FusionResult:
    """Consume duplicate copies and promote exactly one resulting character.

    The caller owns the surrounding transaction. No partial mutation is committed
    by this service if validation fails.
    """
    collection = await session.scalar(
        select(GameCollection).where(
            GameCollection.profile_id == profile_id,
            GameCollection.character_id == character_id,
        ).with_for_update()
    )
    if collection is None:
        raise ValueError("Character is not in the collection")

    rule, remaining = consume_for_fusion(collection.rarity, collection.copies)
    collection.copies = remaining

    # The fused character becomes a new single copy at the next rank. Keeping one
    # row per character makes inventory queries cheap and keeps the ledger simple.
    upgraded = await session.scalar(
        select(GameCollection).where(
            GameCollection.profile_id == profile_id,
            GameCollection.character_id == character_id,
            GameCollection.rarity == rule.to_rarity,
        ).with_for_update()
    )
    if upgraded is None:
        upgraded = GameCollection(
            profile_id=profile_id,
            character_id=character_id,
            rarity=rule.to_rarity,
            level=1,
            experience=0,
            evolution_stage=collection.evolution_stage + 1,
            copies=1,
        )
        session.add(upgraded)
    else:
        upgraded.copies += 1
        upgraded.evolution_stage = max(upgraded.evolution_stage, collection.evolution_stage + 1)

    if collection.copies == 0:
        await session.delete(collection)

    return FusionResult(
        character_id=character_id,
        from_rarity=rule.from_rarity,
        to_rarity=rule.to_rarity,
        consumed=rule.copies_required,
        remaining=remaining,
    )
