# -*- coding: utf-8 -*-
"""Puente REST de moderación Discord; no depende de una librería Gateway."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from .auto_moderation import moderate, ModerationDecision
from .group_setup import DiscordGroupSetup
from .discord_community import ImmersiveStrikeEngine
from .superadmin import is_superadmin


@dataclass(frozen=True, slots=True)
class DiscordModerationResult:
    decision: ModerationDecision
    deleted: bool
    sanctioned: bool
    strikes: int = 0
    admin_actions: tuple[tuple[str, str], ...] = ()


class DiscordModerationHandler:
    """Clasifica y aplica primero la acción local; no procesa el contenido después."""

    def __init__(self, client: DiscordGroupSetup, *, strike_store=None) -> None:
        self._client = client
        self._strike_engine = ImmersiveStrikeEngine(strike_store) if strike_store is not None else None

    def handle_message(
        self,
        *,
        guild_id: str,
        channel_id: str,
        message_id: str,
        user_id: str,
        text: str = "",
        image_tags: tuple[str, ...] = (),
        room_key: str = "general",
        burst: bool = False,
        username: str = "",
    ) -> DiscordModerationResult:
        decision = moderate(text, room_key=room_key, image_tags=image_tags)
        if decision.action == "allow":
            return DiscordModerationResult(decision, False, False)

        deleted = False
        sanctioned = False
        self._client.delete_message(channel_id, message_id)
        deleted = True

        strikes = 0
        admin_actions = ()
        if decision.action == "ban":
            if not is_superadmin(user_id, username):
                self._client.ban_member(guild_id, user_id)
                sanctioned = True
        elif self._strike_engine is not None and not is_superadmin(user_id, username):
            record = self._strike_engine.evaluate(guild_id, user_id, decision.reason, burst=burst)
            if record is not None:
                strikes = record.strikes
                action = self._strike_engine.action_for(record)
                if action == "timeout":
                    self._client.timeout_member(guild_id, user_id, (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
                    sanctioned = True
                elif action == "isolate":
                    self._client.timeout_member(guild_id, user_id, (datetime.now(timezone.utc) + timedelta(days=28)).isoformat())
                    sanctioned = True
                    admin_actions = (("🔨 Ban", "strike:ban:" + user_id), ("👢 Kick", "strike:kick:" + user_id), ("💗 Perdonar", "strike:forgive:" + user_id))
        return DiscordModerationResult(decision, deleted, sanctioned, strikes, admin_actions)
