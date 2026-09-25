from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class CardRarity(StrEnum):
    C = "C"
    R = "R"
    SR = "SR"
    SSR = "SSR"
    UR = "UR"


COIN_VALUES: dict[CardRarity, int] = {
    CardRarity.C: 1,
    CardRarity.R: 5,
    CardRarity.SR: 15,
    CardRarity.SSR: 40,
    CardRarity.UR: 100,
}


@dataclass(frozen=True, slots=True)
class CardRegistration:
    card_id: str
    card_code: str
    character_id: str
    character_name: str
    anime_origin: str
    rarity: CardRarity
    asset_path: Path
    source_provider: str = "local"
    collection_points: int = 0
    custom_emoji_id: str | None = None

    @property
    def coin_value(self) -> int:
        return COIN_VALUES[self.rarity]


@dataclass(frozen=True, slots=True)
class CardInventoryView:
    card_id: str
    card_code: str
    quantity: int
    locked_quantity: int
    available_quantity: int
    holder_type: str
    holder_key: str


@dataclass(frozen=True, slots=True)
class TransactionResult:
    transaction_id: int
    idempotency_key: str
    coin_delta: int
    card_delta: int


@dataclass(frozen=True, slots=True)
class BotStateView:
    bot_identity: str
    mode: str
    status: str
    zone_key: str
    table_key: str | None
    chat_id: int | None
    message_thread_id: int | None
    position_x: int
    position_y: int
    energy: int
    cooldown_until: str | None
