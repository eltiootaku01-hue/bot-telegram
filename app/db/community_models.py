from datetime import datetime

from sqlalchemy import BigInteger, String, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(datetime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(datetime, default=datetime.utcnow)
