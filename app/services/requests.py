import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import DomainEvent, FanRequest, GameProfile, RequestStatus
from app.db.repositories import MemberRepository


DEFAULT_REQUEST_COST = 50


@dataclass(frozen=True, slots=True)
class PaidRequestResult:
    request: FanRequest
    remaining_points: int
    created: bool


@dataclass(frozen=True, slots=True)
class RequestQueueSummary:
    pending: int
    processing: int
    overdue: int
    completed_recent: int
    oldest_pending_at: datetime | None


def _is_fan_request_source_conflict(exc: IntegrityError) -> bool:
    """Recognize only the unique constraint used for request idempotency."""
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_fan_request_source":
        return True
    message = str(exc.orig).lower()
    return "uq_fan_request_source" in message or (
        "fan_requests.user_id" in message
        and "fan_requests.chat_id" in message
        and "fan_requests.source_message_id" in message
    )


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
    ) -> PaidRequestResult | None:
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
                    select(GameProfile).where(
                        GameProfile.user_id == user_id,
                        GameProfile.chat_id == chat_id,
                    )
                )
                return PaidRequestResult(
                    request=existing,
                    remaining_points=profile.points if profile else 0,
                    created=False,
                )

        nested = await session.begin_nested()
        try:
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

            remaining = await MemberRepository().spend_points(
                session,
                user_id=user_id,
                chat_id=chat_id,
                amount=points_cost,
                reason="Pedido de fan",
                reference_type="fan_request",
                reference_id=str(request.id),
                commit=False,
            )
            if remaining is None:
                await nested.rollback()
                return None

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
            await nested.commit()
        except IntegrityError as exc:
            await nested.rollback()
            if source_message_id is None or not _is_fan_request_source_conflict(exc):
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
                select(GameProfile).where(
                    GameProfile.user_id == user_id,
                    GameProfile.chat_id == chat_id,
                )
            )
            return PaidRequestResult(
                request=existing,
                remaining_points=profile.points if profile else 0,
                created=False,
            )

        await session.refresh(request)
        return PaidRequestResult(
            request=request,
            remaining_points=remaining,
            created=True,
        )

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
                FanRequest.status.in_([
                    RequestStatus.NEW.value,
                    RequestStatus.NEEDS_INFO.value,
                    RequestStatus.PENDING_ADMIN.value,
                ])
            )
            .order_by(FanRequest.created_at.asc())
            .limit(limit)
        )
        return list(result)

    async def for_user(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int | None = None,
        limit: int = 10,
    ) -> list[FanRequest]:
        if limit <= 0:
            return []
        statement = (
            select(FanRequest)
            .where(FanRequest.user_id == user_id)
            .order_by(FanRequest.id.desc())
            .limit(limit)
        )
        if chat_id is not None:
            statement = statement.where(FanRequest.chat_id == chat_id)
        return list(await session.scalars(statement))

    async def queue_summary(
        self,
        session: AsyncSession,
        *,
        chat_id: int | None = None,
        completed_since: datetime | None = None,
    ) -> "RequestQueueSummary":
        now = utc_now()
        base = [FanRequest.chat_id == chat_id] if chat_id is not None else []
        pending_statuses = (
            RequestStatus.NEW.value,
            RequestStatus.NEEDS_INFO.value,
            RequestStatus.PENDING_ADMIN.value,
        )
        completed_since = completed_since or now.replace(hour=0, minute=0, second=0, microsecond=0)

        pending = await session.scalar(
            select(func.count(FanRequest.id)).where(
                *base, FanRequest.status.in_(pending_statuses)
            )
        )
        processing = await session.scalar(
            select(func.count(FanRequest.id)).where(
                *base, FanRequest.status == RequestStatus.PROCESSING.value
            )
        )
        overdue = await session.scalar(
            select(func.count(FanRequest.id)).where(
                *base,
                FanRequest.status.in_(
                    pending_statuses
                    + (
                        RequestStatus.APPROVED.value,
                        RequestStatus.SCHEDULED.value,
                        RequestStatus.PROCESSING.value,
                    )
                ),
                FanRequest.due_at.is_not(None),
                FanRequest.due_at < now,
            )
        )
        completed_recent = await session.scalar(
            select(func.count(FanRequest.id)).where(
                *base,
                FanRequest.status == RequestStatus.COMPLETED.value,
                FanRequest.updated_at >= completed_since,
            )
        )
        oldest = await session.scalar(
            select(func.min(FanRequest.created_at)).where(
                *base, FanRequest.status.in_(pending_statuses)
            )
        )
        return RequestQueueSummary(
            pending=int(pending or 0),
            processing=int(processing or 0),
            overdue=int(overdue or 0),
            completed_recent=int(completed_recent or 0),
            oldest_pending_at=oldest,
        )

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
        request.updated_at = utc_now()
        if admin_note is not None:
            request.admin_note = admin_note
        if due_at is not None:
            request.due_at = due_at
        await session.flush()
        return request
