import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DomainEvent, FanRequest, GameProfile, PointTransaction, RequestStatus


DEFAULT_REQUEST_COST = 50


class RequestService:
    """Persistence boundary for fan requests; the web panel can reuse it later."""

    async def create_paid(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        description: str,
        points_cost: int = DEFAULT_REQUEST_COST,
        character_id: str | None = None,
        special_details: str | None = None,
        source_message_id: int | None = None,
    ) -> tuple[FanRequest, int] | None:
        if not description.strip():
            raise ValueError("Request description cannot be empty")
        if points_cost <= 0:
            raise ValueError("Request cost must be positive")

        if source_message_id is not None:
            existing = await session.scalar(
                select(FanRequest).where(
                    FanRequest.user_id == user_id,
                    FanRequest.chat_id == chat_id,
                    FanRequest.source_message_id == source_message_id,
                )
            )
            if existing is not None:
                profile = await session.scalar(
                    select(GameProfile).where(GameProfile.user_id == user_id, GameProfile.chat_id == chat_id)
                )
                return existing, profile.points if profile else 0

        profile = await session.scalar(
            select(GameProfile).where(GameProfile.user_id == user_id, GameProfile.chat_id == chat_id)
        )
        if profile is None:
            profile = GameProfile(user_id=user_id, chat_id=chat_id)
            session.add(profile)
            await session.flush()
        if profile.points < points_cost:
            return None

        profile.points -= points_cost
        profile.updated_at = datetime.utcnow()
        request = FanRequest(
            user_id=user_id,
            chat_id=chat_id,
            description=description.strip(),
            character_id=character_id,
            special_details=special_details,
            points_cost=points_cost,
            source_message_id=source_message_id,
            status=RequestStatus.PENDING_ADMIN.value,
        )
        session.add(request)
        await session.flush()
        session.add(
            PointTransaction(
                user_id=user_id,
                chat_id=chat_id,
                amount=-points_cost,
                reason="Pedido de fan",
                reference_type="fan_request",
                reference_id=str(request.id),
            )
        )
        session.add(
            DomainEvent(
                event_id=f"fan-request-created:{request.id}",
                event_type="fan_request.created",
                payload=json.dumps(
                    {
                        "request_id": request.id,
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "description": request.description,
                        "points_cost": points_cost,
                        "character_id": character_id,
                        "special_details": special_details,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            if source_message_id is None:
                raise
            existing = await session.scalar(
                select(FanRequest).where(
                    FanRequest.user_id == user_id,
                    FanRequest.chat_id == chat_id,
                    FanRequest.source_message_id == source_message_id,
                )
            )
            if existing is None:
                raise
            profile = await session.scalar(
                select(GameProfile).where(GameProfile.user_id == user_id, GameProfile.chat_id == chat_id)
            )
            return existing, profile.points if profile else 0
        await session.refresh(request)
        return request, profile.points

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        description: str,
        points_cost: int = DEFAULT_REQUEST_COST,
        character_id: str | None = None,
        special_details: str | None = None,
        source_message_id: int | None = None,
    ) -> FanRequest:
        if not description.strip():
            raise ValueError("Request description cannot be empty")
        if points_cost < 0:
            raise ValueError("Request cost cannot be negative")
        request = FanRequest(
            user_id=user_id,
            chat_id=chat_id,
            description=description.strip(),
            character_id=character_id,
            special_details=special_details,
            points_cost=points_cost,
            source_message_id=source_message_id,
            status=RequestStatus.NEW.value,
        )
        session.add(request)
        await session.flush()
        return request

    async def get(self, session: AsyncSession, request_id: int) -> FanRequest | None:
        return await session.get(FanRequest, request_id)

    async def pending(self, session: AsyncSession, limit: int = 50) -> list[FanRequest]:
        result = await session.scalars(
            select(FanRequest)
            .where(
                FanRequest.status.in_([RequestStatus.NEW.value, RequestStatus.NEEDS_INFO.value, RequestStatus.PENDING_ADMIN.value])
            )
            .order_by(FanRequest.created_at.asc())
            .limit(limit)
        )
        return list(result)

    async def set_status(
        self,
        session: AsyncSession,
        request_id: int,
        status: RequestStatus,
        *,
        admin_note: str | None = None,
        due_at: datetime | None = None,
    ) -> FanRequest | None:
        request = await session.get(FanRequest, request_id)
        if request is None:
            return None
        request.status = status.value
        request.updated_at = datetime.utcnow()
        if admin_note is not None:
            request.admin_note = admin_note
        if due_at is not None:
            request.due_at = due_at
        await session.flush()
        return request
