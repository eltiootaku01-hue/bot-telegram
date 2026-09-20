from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import HumanVerification


_PERMISSION_FIELDS = (
    "can_send_messages",
    "can_send_audios",
    "can_send_documents",
    "can_send_photos",
    "can_send_videos",
    "can_send_video_notes",
    "can_send_voice_notes",
    "can_send_polls",
    "can_send_other_messages",
    "can_add_web_page_previews",
)


def permissions_to_json(permissions: Any) -> str:
    """Persist Telegram's default member permissions without coupling the DB to aiogram."""
    payload = {
        field: getattr(permissions, field, None)
        for field in _PERMISSION_FIELDS
        if getattr(permissions, field, None) is not None
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def permissions_from_json(raw: str) -> dict[str, bool]:
    try:
        payload = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return {
        key: bool(value)
        for key, value in payload.items()
        if key in _PERMISSION_FIELDS and isinstance(value, bool)
    }


class HumanVerificationService:
    """Transactional state machine for Chie's one-click human verification."""

    async def begin(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        user_id: int,
        prompt_message_id: int | None,
        default_permissions_json: str,
        timeout_seconds: int = 120,
        now: datetime | None = None,
    ) -> HumanVerification:
        if timeout_seconds < 30:
            raise ValueError("timeout_seconds must be at least 30")
        current = now or utc_now()
        row = await session.scalar(
            select(HumanVerification).where(
                HumanVerification.chat_id == chat_id,
                HumanVerification.user_id == user_id,
            )
        )
        expires_at = current + timedelta(seconds=timeout_seconds)
        if row is None:
            row = HumanVerification(
                chat_id=chat_id,
                user_id=user_id,
                status="pending",
                prompt_message_id=prompt_message_id,
                default_permissions_json=default_permissions_json,
                prompted_at=current,
                expires_at=expires_at,
                updated_at=current,
            )
            session.add(row)
        else:
            row.status = "pending"
            row.prompt_message_id = prompt_message_id
            row.default_permissions_json = default_permissions_json
            row.prompted_at = current
            row.expires_at = expires_at
            row.decided_at = None
            row.updated_at = current
        await session.flush()
        return row

    async def claim_expired(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        limit: int = 50,
    ) -> list[HumanVerification]:
        """Claim overdue verifications without racing a user's button click."""
        current = now or utc_now()
        if limit <= 0:
            return []
        candidates = list(
            await session.scalars(
                select(HumanVerification)
                .where(
                    HumanVerification.status.in_(("pending", "expiring")),
                    HumanVerification.expires_at.is_not(None),
                    HumanVerification.expires_at <= current,
                )
                .order_by(HumanVerification.id.asc())
                .limit(limit)
            )
        )
        claimed: list[HumanVerification] = []
        for row in candidates:
            result = await session.execute(
                update(HumanVerification)
                .where(
                    HumanVerification.id == row.id,
                    HumanVerification.status.in_(("pending", "expiring")),
                    HumanVerification.expires_at.is_not(None),
                    HumanVerification.expires_at <= current,
                )
                .values(status="expiring", updated_at=current)
            )
            if result.rowcount == 1:
                claimed.append(row)
        if claimed:
            await session.commit()
        return claimed

    async def finish_expiration(
        self,
        session: AsyncSession,
        *,
        verification_id: int,
        expired_at: datetime | None = None,
    ) -> bool:
        current = expired_at or utc_now()
        result = await session.execute(
            update(HumanVerification)
            .where(
                HumanVerification.id == verification_id,
                HumanVerification.status == "expiring",
            )
            .values(
                status="expired",
                decided_at=current,
                updated_at=current,
            )
        )
        return result.rowcount == 1

    async def requeue_expiration(
        self,
        session: AsyncSession,
        *,
        verification_id: int,
        now: datetime | None = None,
    ) -> bool:
        current = now or utc_now()
        result = await session.execute(
            update(HumanVerification)
            .where(
                HumanVerification.id == verification_id,
                HumanVerification.status == "expiring",
            )
            .values(status="pending", expires_at=current + timedelta(seconds=30), updated_at=current)
        )
        return result.rowcount == 1

    async def decide(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        user_id: int,
        status: str,
        now: datetime | None = None,
    ) -> HumanVerification | None:
        if status not in {"verified", "rejected"}:
            raise ValueError("verification status must be verified or rejected")
        current = now or utc_now()
        result = await session.execute(
            update(HumanVerification)
            .where(
                HumanVerification.chat_id == chat_id,
                HumanVerification.user_id == user_id,
                HumanVerification.status == "pending",
            )
            .values(
                status=status,
                decided_at=current,
                updated_at=current,
            )
        )
        if result.rowcount != 1:
            return None
        return await session.scalar(
            select(HumanVerification).where(
                HumanVerification.chat_id == chat_id,
                HumanVerification.user_id == user_id,
            )
        )
