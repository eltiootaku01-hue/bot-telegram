from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RareDropApproval


# Everything above public C is exceptional. The owner is asked privately
# before the drop can be awarded to a player.
HIGH_RARITIES = {"B", "A", "S", "SS", "SSS"}


async def propose(
    session: AsyncSession,
    *,
    character_id: str,
    rarity: str,
    target_user_id: int,
    target_chat_id: int,
) -> RareDropApproval:
    """Create a private approval request; caller must notify the configured owner."""
    if rarity not in HIGH_RARITIES:
        raise ValueError("Only B/A/S/SS/SSS drops require private approval")
    request = RareDropApproval(
        character_id=character_id,
        rarity=rarity,
        target_user_id=target_user_id,
        target_chat_id=target_chat_id,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def decide(session: AsyncSession, approval_id: int, approved: bool) -> RareDropApproval | None:
    request = await session.scalar(select(RareDropApproval).where(RareDropApproval.id == approval_id))
    if request is None or request.status != "pending":
        return None
    request.status = "approved" if approved else "rejected"
    request.decided_at = datetime.utcnow()
    await session.commit()
    return request
