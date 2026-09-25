from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.identity import BotIdentity
from app.core.time import utc_now
from app.db.models import Base


class CardHolderType(StrEnum):
    USER = "user"
    BANK = "bank"
    BOT = "bot"


class BotRuntimeMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class BotState(Base):
    """Durable state exposed to Casa de Comando for one autonomous identity."""

    __tablename__ = "bot_states"
    __table_args__ = (
        UniqueConstraint("bot_identity", name="uq_bot_state_identity"),
        CheckConstraint(
            "mode IN ('manual', 'automatic')",
            name="ck_bot_state_mode",
        ),
        CheckConstraint(
            "energy >= 0",
            name="ck_bot_state_energy_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_identity: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16), default=BotRuntimeMode.AUTOMATIC.value)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    zone_key: Mapped[str] = mapped_column(String(64), default="cafe")
    table_key: Mapped[str | None] = mapped_column(String(64))
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    message_thread_id: Mapped[int | None] = mapped_column(BigInteger)
    position_x: Mapped[int] = mapped_column(Integer, default=0)
    position_y: Mapped[int] = mapped_column(Integer, default=0)
    energy: Mapped[int] = mapped_column(Integer, default=100)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime)
    state_json: Mapped[str] = mapped_column(String(8000), default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CardInventory(Base):
    """Generic card holding used for players, the bank and bot-owned collections."""

    __tablename__ = "card_inventory"
    __table_args__ = (
        UniqueConstraint(
            "holder_type",
            "holder_key",
            "card_id",
            name="uq_card_inventory_holder_card",
        ),
        CheckConstraint(
            "quantity >= 0 AND locked_quantity >= 0 AND locked_quantity <= quantity",
            name="ck_card_inventory_quantities",
        ),
        CheckConstraint(
            "holder_type IN ('user', 'bank', 'bot')",
            name="ck_card_inventory_holder_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(
        ForeignKey("card_definitions.id", ondelete="CASCADE")
    )
    holder_type: Mapped[str] = mapped_column(String(16))
    holder_key: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    locked_quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class TransactionHistory(Base):
    """Immutable audit ledger for cards and Café Coins."""

    __tablename__ = "transaction_history"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_transaction_history_idempotency",
        ),
        CheckConstraint(
            "coin_delta <> 0 OR card_delta <> 0",
            name="ck_transaction_history_nonzero",
        ),
        CheckConstraint(
            "card_delta = 0 OR card_id IS NOT NULL",
            name="ck_transaction_history_card_required",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    transaction_type: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    card_id: Mapped[str | None] = mapped_column(
        ForeignKey("card_definitions.id", ondelete="SET NULL")
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    coin_delta: Mapped[int] = mapped_column(Integer, default=0)
    card_delta: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(64), default="system")
    reference_type: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[str] = mapped_column(String(8000), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


def validate_bot_identity(value: str) -> BotIdentity:
    """Convert a persisted identity to the application's canonical enum."""
    return BotIdentity(value)
