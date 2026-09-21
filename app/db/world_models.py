from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.models import Base


class WorldCatalogEntry(Base):
    """Definition of a topic/action/scene that exists in Ciudad Animals."""

    __tablename__ = "world_catalog"
    __table_args__ = (
        UniqueConstraint("bot_identity", "entry_type", "entry_key", name="uq_world_catalog_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_identity: Mapped[str] = mapped_column(String(32))
    entry_type: Mapped[str] = mapped_column(String(32))
    entry_key: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WorldUsageStat(Base):
    """Small aggregate dictionary of what users and the world actually use."""

    __tablename__ = "world_usage_stats"
    __table_args__ = (
        UniqueConstraint(
            "bot_identity",
            "scope_type",
            "scope_id",
            "entry_type",
            "entry_key",
            name="uq_world_usage_scope_entry",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_identity: Mapped[str] = mapped_column(String(32))
    scope_type: Mapped[str] = mapped_column(String(32))
    scope_id: Mapped[str] = mapped_column(String(128))
    entry_type: Mapped[str] = mapped_column(String(32))
    entry_key: Mapped[str] = mapped_column(String(128))
    count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WorldReview(Base):
    """Persisted aggregate review snapshot; contains no raw conversation text."""

    __tablename__ = "world_reviews"
    __table_args__ = (
        UniqueConstraint(
            "review_type",
            "period_key",
            name="uq_world_review_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_type: Mapped[str] = mapped_column(String(32))
    period_key: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    report_json: Mapped[str] = mapped_column(String(20000))


class WorldProposal(Base):
    """Untrusted AI or human proposal linked to a review; never changes canon itself."""

    __tablename__ = "world_proposals"
    __table_args__ = (
        UniqueConstraint(
            "review_id",
            "generator",
            name="uq_world_proposal_generator",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(Integer)
    generator: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    payload_json: Mapped[str] = mapped_column(String(30000))


class GameWorldEvent(Base):
    """Durable presentation event owned by the game world, not by a character."""

    __tablename__ = "game_world_events"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_game_world_event_dedupe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(64))
    dedupe_key: Mapped[str] = mapped_column(String(255))
    chat_id: Mapped[int] = mapped_column(Integer)
    presenter_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    payload_json: Mapped[str] = mapped_column(String(12000), default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    run_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    message_id: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
