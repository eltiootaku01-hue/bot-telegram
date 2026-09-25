from __future__ import annotations
import time
from dataclasses import dataclass
from .models import ConversationIntent, ConversationSnapshot, ConversationState

_ALLOWED = {
 "cari": frozenset({ConversationState.IDLE, ConversationState.IN_POKER_GAME, ConversationState.BUSY_AT_TABLE, ConversationState.COOLDOWN}),
 "sunna": frozenset({ConversationState.IDLE, ConversationState.PROCESSING_ROLL, ConversationState.CARD_CLAIM_ACTIVE, ConversationState.COOLDOWN}),
 "cami": frozenset({ConversationState.IDLE, ConversationState.BROWSING_CATALOG, ConversationState.PROCESSING_INVENTORY}),
 "chie": frozenset({ConversationState.IDLE, ConversationState.CAMPANA_COOLDOWN, ConversationState.SECURITY_LOCKOUT}),
}

@dataclass(slots=True)
class _Entry:
    state: ConversationState
    cooldown_until: float | None = None

class StateStore:
    """Identity-partitioned in-memory FSM. No I/O."""
    def __init__(self, *, clock=time.monotonic) -> None:
        self._clock = clock
        self._states: dict[tuple[str, int], _Entry] = {}

    def _identity(self, identity: str) -> str:
        key = identity.casefold().strip()
        if key not in _ALLOWED:
            raise ValueError(f"Unsupported identity: {identity}")
        return key

    def snapshot(self, identity: str, user_id: int) -> ConversationSnapshot:
        key = self._identity(identity)
        storage_key = (key, int(user_id))
        entry = self._states.get(storage_key)
        if entry is None:
            return ConversationSnapshot(key, int(user_id), ConversationState.IDLE)
        if entry.cooldown_until is not None and entry.cooldown_until <= self._clock():
            entry.state, entry.cooldown_until = ConversationState.IDLE, None
        return ConversationSnapshot(key, int(user_id), entry.state, entry.cooldown_until)

    def remaining(self, identity: str, user_id: int) -> int:
        self._identity(identity)
        entry = self._states.get((identity.casefold().strip(), int(user_id)))
        if not entry or entry.cooldown_until is None:
            return 0
        return max(0, int(entry.cooldown_until - self._clock() + 0.999))

    def transition(self, identity: str, user_id: int, intent: ConversationIntent | str, *, cooldown_seconds: int = 0) -> ConversationSnapshot:
        identity = self._identity(identity)
        current = self.snapshot(identity, user_id)
        intent = ConversationIntent(intent)

        if identity == "cari" and intent is ConversationIntent.GAME_INVITE:
            if current.state is ConversationState.IN_POKER_GAME: raise ValueError("GAME_ALREADY_ACTIVE")
            if current.state is ConversationState.COOLDOWN: raise ValueError("COOLDOWN_ACTIVE")
            next_state = ConversationState.IN_POKER_GAME
        elif identity == "sunna" and intent is ConversationIntent.GACHA_ROLL:
            if current.state in {ConversationState.PROCESSING_ROLL, ConversationState.CARD_CLAIM_ACTIVE}: raise ValueError("ROLL_ALREADY_ACTIVE")
            next_state = ConversationState.PROCESSING_ROLL
        elif identity == "sunna" and intent is ConversationIntent.CLAIM_CARD:
            if current.state in {ConversationState.PROCESSING_ROLL, ConversationState.CARD_CLAIM_ACTIVE}: raise ValueError("CLAIM_ALREADY_ACTIVE")
            next_state = ConversationState.CARD_CLAIM_ACTIVE
        elif identity == "cami" and intent is ConversationIntent.CATALOG_QUERY:
            if current.state is not ConversationState.IDLE: raise ValueError("CATALOG_BUSY")
            next_state = ConversationState.BROWSING_CATALOG
        elif identity == "cami" and intent is ConversationIntent.INVENTORY_SEARCH:
            if current.state is not ConversationState.IDLE: raise ValueError("INVENTORY_BUSY")
            next_state = ConversationState.PROCESSING_INVENTORY
        elif identity == "chie" and intent in {ConversationIntent.CAMPANA, ConversationIntent.CAMPANA_FULL}:
            if current.state is ConversationState.CAMPANA_COOLDOWN: raise ValueError("CAMPANA_COOLDOWN")
            next_state = ConversationState.CAMPANA_COOLDOWN
        elif intent is ConversationIntent.STATUS_QUERY:
            next_state = current.state
        else:
            next_state = current.state

        until = self._clock() + cooldown_seconds if next_state in {ConversationState.COOLDOWN, ConversationState.CAMPANA_COOLDOWN} and cooldown_seconds > 0 else None
        self._states[(identity, int(user_id))] = _Entry(next_state, until)
        return self.snapshot(identity, user_id)

    def release(self, identity: str, user_id: int) -> ConversationSnapshot:
        identity = self._identity(identity)
        self._states[(identity, int(user_id))] = _Entry(ConversationState.IDLE)
        return self.snapshot(identity, user_id)
