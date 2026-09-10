from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameCollection
from app.game.evolution import next_fusion


@dataclass(frozen=True, slots=True)
class FusionResult:
    character_id: str
    from_rarity: str
    to_rarity: str
    consumed: int
    remaining: int


async def fuse_collection(session: AsyncSession, *, profile_id: int, character_id: str) -> FusionResult:
    """Promote a collection row with a conditional, race-safe state transition."""
    collection = await session.scalar(
        select(GameCollection).where(
            GameCollection.profile_id == profile_id,
            GameCollection.character_id == character_id,
        )
    )
    if collection is None:
        raise ValueError("Character is not in the collection")

    rule = next_fusion(collection.rarity)
    if rule is None:
        raise ValueError("This character cannot evolve further")
    if collection.copies < rule.copies_required:
        raise ValueError(f"Need {rule.copies_required} copies to evolve")

    result = await session.execute(
        update(GameCollection)
        .where(
            GameCollection.id == collection.id,
            GameCollection.rarity == rule.from_rarity,
            GameCollection.copies >= rule.copies_required,
        )
        .values(
            copies=GameCollection.copies - rule.copies_required + 1,
            rarity=rule.to_rarity,
            level=1,
            experience=0,
            evolution_stage=GameCollection.evolution_stage + 1,
        )
    )
    if result.rowcount != 1:
        raise ValueError("La fusión ya fue realizada o cambió el inventario")

    await session.flush()
    updated = await session.get(GameCollection, collection.id)
    remaining = updated.copies if updated is not None else 0
    return FusionResult(
        character_id=character_id,
        from_rarity=rule.from_rarity,
        to_rarity=rule.to_rarity,
        consumed=rule.copies_required,
        remaining=remaining,
    )
