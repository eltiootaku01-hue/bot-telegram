from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class ForumTopic(Base):
    """Persistent mapping between a community topic and Telegram thread id."""

    __tablename__ = "forum_topics"
    __table_args__ = (UniqueConstraint("chat_id", "topic_key", name="uq_forum_topic_chat_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    topic_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(128))
    thread_id: Mapped[int] = mapped_column(BigInteger)
    bot_identity: Mapped[str] = mapped_column(String(32), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SetupSession(Base):
    __tablename__ = "setup_sessions"
    __table_args__ = (UniqueConstraint("user_id", "bot_identity", name="uq_setup_user_bot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    bot_identity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="awaiting_admin")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
