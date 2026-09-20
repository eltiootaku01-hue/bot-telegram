from __future__ import annotations

import json
from datetime import datetime
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
        now: datetime | None = None,
    ) -> HumanVerification:
        current = now or utc_now()
        row = await session.scalar(
            select(HumanVerification).where(
                HumanVerification.chat_id == chat_id,
                HumanVerification.user_id == user_id,
            )
        )
        if row is None:
            row = HumanVerification(
                chat_id=chat_id,
                user_id=user_id,
                status="pending",
                prompt_message_id=prompt_message_id,
                default_permissions_json=default_permissions_json,
                prompted_at=current,
                updated_at=current,
            )
            session.add(row)
        else:
            row.status = "pending"
            row.prompt_message_id = prompt_message_id
            row.default_permissions_json = default_permissions_json
            row.prompted_at = current
            row.decided_at = None
            row.updated_at = current
        await session.flush()
        return row

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
