from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(255), default="")
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    is_bot: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(32), default="unknown")
    title: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserChat(Base):
    """Durable membership/activity relationship; game state is kept separate."""

    __tablename__ = "user_chats"
    __table_args__ = (UniqueConstraint("user_id", "chat_id", name="uq_user_chat"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="member")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime)
    left_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GameProfile(Base):
    """One durable player profile per Telegram user/chat pair."""

    __tablename__ = "game_profiles"
    __table_args__ = (UniqueConstraint("user_id", "chat_id", name="uq_game_profile"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    level: Mapped[int] = mapped_column(Integer, default=1)
    experience: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BotSetting(Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int | None] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(4000), default="")
