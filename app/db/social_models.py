from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.models import Base


class SocialWakeReason(StrEnum):
    SCHEDULED = "scheduled"
    EVENT = "event"
    MANUAL = "manual"


class SocialWake(Base):
    """Durable per-chat wake state for proactive social behavior.

    The wake is an opportunity to inspect the chat, not a command to speak.
    Keeping this separate from the in-memory controller lets restarts preserve
    the next social check and its silence backoff.
    """

    __tablename__ = "social_wakes"
    __table_args__ = (UniqueConstraint("chat_id", name="uq_social_wake_chat"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    next_wake_at: Mapped[datetime] = mapped_column(DateTime)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime)
    pending_reason: Mapped[str | None] = mapped_column(String(32))
    consecutive_silences: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
