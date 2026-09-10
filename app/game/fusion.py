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
    """Consume duplicate copies and promote the single collection row atomically."""
    collection = await session.scalar(
        select(GameCollection).where(
            GameCollection.profile_id == profile_id,
            GameCollection.character_id == character_id,
        ).with_for_update()
    )
    if collection is None:
        raise ValueError("Character is not in the collection")

    rule, remaining = consume_for_fusion(collection.rarity, collection.copies)
    collection.copies = remaining + 1
    collection.rarity = rule.to_rarity
    collection.level = 1
    collection.experience = 0
    collection.evolution_stage += 1

    return FusionResult(
        character_id=character_id,
        from_rarity=rule.from_rarity,
        to_rarity=rule.to_rarity,
        consumed=rule.copies_required,
        remaining=remaining + 1,
    )
