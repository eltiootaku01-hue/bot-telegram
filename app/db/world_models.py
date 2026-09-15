from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.models import Base


class WorldCatalogEntry(Base):
    """Definition of a topic/action/scene that exists in Ciudad Animals."""

    __tablename__ = "world_catalog"
    __table_args__ = (UniqueConstraint("bot_identity", "entry_type", "entry_key", name="uq_world_catalog_entry"),)

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
