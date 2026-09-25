from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class ConversationState(StrEnum):
    IDLE = "IDLE"
    IN_POKER_GAME = "IN_POKER_GAME"
    BUSY_AT_TABLE = "BUSY_AT_TABLE"
    COOLDOWN = "COOLDOWN"
    PROCESSING_ROLL = "PROCESSING_ROLL"
    CARD_CLAIM_ACTIVE = "CARD_CLAIM_ACTIVE"
    BROWSING_CATALOG = "BROWSING_CATALOG"
    PROCESSING_INVENTORY = "PROCESSING_INVENTORY"
    CAMPANA_COOLDOWN = "CAMPANA_COOLDOWN"
    SECURITY_LOCKOUT = "SECURITY_LOCKOUT"

class ConversationIntent(StrEnum):
    GREETING = "GREETING"
    STATUS_QUERY = "STATUS_QUERY"
    GAME_INVITE = "GAME_INVITE"
    CAMPANA = "CAMPANA"
    GACHA_ROLL = "GACHA_ROLL"
    CLAIM_CARD = "CLAIM_CARD"
    VIEW_RATES = "VIEW_RATES"
    INVENTORY_SEARCH = "INVENTORY_SEARCH"
    CATALOG_QUERY = "CATALOG_QUERY"
    MINI_APP_OPEN = "MINI_APP_OPEN"
    CAMPANA_FULL = "CAMPANA_FULL"
    SECURITY_STATUS = "SECURITY_STATUS"
    HELP_SYSTEM = "HELP_SYSTEM"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True, slots=True)
class ConversationSnapshot:
    identity: str
    user_id: int
    state: ConversationState
    cooldown_until: float | None = None

@dataclass(frozen=True, slots=True)
class ParseResult:
    intent: ConversationIntent
    matched_token: str | None = None
