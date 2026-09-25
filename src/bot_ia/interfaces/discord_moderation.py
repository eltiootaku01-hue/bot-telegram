# -*- coding: utf-8 -*-
"""Puente REST de moderación Discord; no depende de una librería Gateway."""

from __future__ import annotations

from dataclasses import dataclass
from .auto_moderation import moderate, ModerationDecision
from .group_setup import DiscordGroupSetup


@dataclass(frozen=True, slots=True)
class DiscordModerationResult:
    decision: ModerationDecision
    deleted: bool
    sanctioned: bool


class DiscordModerationHandler:
    """Clasifica y aplica primero la acción local; no procesa el contenido después."""

    def __init__(self, client: DiscordGroupSetup) -> None:
        self._client = client

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
    ) -> DiscordModerationResult:
        decision = moderate(text, room_key=room_key, image_tags=image_tags)
        if decision.action == "allow":
            return DiscordModerationResult(decision, False, False)

        deleted = False
        sanctioned = False
        self._client.delete_message(channel_id, message_id)
        deleted = True

        if decision.action == "ban":
            self._client.ban_member(guild_id, user_id)
            sanctioned = True

        return DiscordModerationResult(decision, deleted, sanctioned)
