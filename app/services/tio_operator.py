from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import Chat, TioOperatorRequest, User


@dataclass(frozen=True, slots=True)
class TioOperatorResult:
    request: TioOperatorRequest
    created: bool


class TioOperatorService:
    """Persistent bridge from explicit Tío Otaku mentions to the human operator."""

    async def capture(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        user_id: int,
        source_message_id: int,
        text: str,
    ) -> TioOperatorResult:
        text = text.strip()
        if len(text) < 2:
            raise ValueError("Operator message cannot be empty")

        existing = await session.scalar(
            select(TioOperatorRequest).where(
                TioOperatorRequest.chat_id == chat_id,
                TioOperatorRequest.source_message_id == source_message_id,
            )
        )
        if existing is not None:
            return TioOperatorResult(existing, False)

        row = TioOperatorRequest(
            chat_id=chat_id,
            user_id=user_id,
            source_message_id=source_message_id,
            text=text[:4000],
            status="pending",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(TioOperatorRequest).where(
                    TioOperatorRequest.chat_id == chat_id,
                    TioOperatorRequest.source_message_id == source_message_id,
                )
            )
            if existing is None:
                raise
            return TioOperatorResult(existing, False)

        return TioOperatorResult(row, True)

    async def decide(
        self,
        session: AsyncSession,
        *,
        request_id: int,
        status: str,
    ) -> bool:
        if status not in {"acknowledged", "resolved"}:
            raise ValueError("Unsupported operator request status")
        allowed_current = (
            ("pending",)
            if status == "acknowledged"
            else ("pending", "acknowledged")
        )
        result = await session.execute(
            update(TioOperatorRequest)
            .where(
                TioOperatorRequest.id == request_id,
                TioOperatorRequest.status.in_(allowed_current),
            )
            .values(status=status, updated_at=utc_now())
        )
        return result.rowcount == 1

    async def recent_pending(
        self,
        session: AsyncSession,
        *,
        limit: int = 10,
    ) -> list[TioOperatorRequest]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        result = await session.scalars(
            select(TioOperatorRequest)
            .where(TioOperatorRequest.status.in_(("pending", "acknowledged")))
            .order_by(TioOperatorRequest.id.desc())
            .limit(limit)
        )
        return list(result)

    async def context(
        self,
        session: AsyncSession,
        request: TioOperatorRequest,
    ) -> tuple[User | None, Chat | None]:
        user = await session.get(User, request.user_id)
        chat = await session.get(Chat, request.chat_id)
        return user, chat
