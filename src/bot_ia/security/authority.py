# -*- coding: utf-8 -*-
"""Autoridad central de acceso para interfaces remotas de BOT-IA."""

from __future__ import annotations

from dataclasses import dataclass
import os

from bot_ia.interfaces.telegram_security import (
    is_authorized_admin_destination,
    is_authorized_telegram_forum_route,
    is_authorized_telegram_group,
)


def _env_ids(*names: str) -> frozenset[str]:
    values: set[str] = set()
    for name in names:
        raw = os.getenv(name, "")
        values.update(value.strip() for value in raw.split(",") if value.strip())
    return frozenset(values)


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    platform: str
    user_id: str
    action: str
    destination_id: str = ""
    destination_kind: str = "dm"
    thread_id: int | None = None
    is_topic: bool = False
    requires_admin: bool = False
    require_authorized_destination: bool = False


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    permission: str = "public"


class AuthorityCore:
    """Fuente única para identidad estable, destino y permiso de acción."""

    TELEGRAM = "telegram"
    DISCORD = "discord"

    def admin_user_ids(self, platform: str) -> frozenset[str]:
        normalized = str(platform).strip().casefold()
        if normalized == self.TELEGRAM:
            return _env_ids("TELEGRAM_ADMIN_USER_IDS", "TELEGRAM_SUPERADMIN_ID")
        if normalized == self.DISCORD:
            return _env_ids("DISCORD_ADMIN_USER_IDS", "DISCORD_SUPERADMIN_USER_ID")
        return frozenset()

    def is_superadmin(self, platform: str, user_id: str) -> bool:
        normalized = str(platform).strip().casefold()
        uid = str(user_id).strip()
        if not uid:
            return False
        if normalized == self.TELEGRAM:
            return uid in _env_ids("TELEGRAM_SUPERADMIN_ID")
        if normalized == self.DISCORD:
            return uid in _env_ids("DISCORD_SUPERADMIN_USER_ID")
        return False

    def is_admin(self, platform: str, user_id: str) -> bool:
        uid = str(user_id).strip()
        return bool(uid and uid in self.admin_user_ids(platform))

    @staticmethod
    def authorized_discord_guild_ids() -> frozenset[str]:
        return _env_ids("DISCORD_AUTHORIZED_GUILD_IDS")

    def is_authorized_discord_guild(self, guild_id: str) -> bool:
        clean_guild = str(guild_id).strip()
        return bool(clean_guild and clean_guild in self.authorized_discord_guild_ids())

    def _authorize_destination(self, request: AuthorizationRequest) -> AuthorizationDecision:
        platform = request.platform.strip().casefold()
        destination = request.destination_id.strip()
        kind = request.destination_kind.strip().casefold()
        if not destination:
            return AuthorizationDecision(False, "destino vacío")

        if platform == self.TELEGRAM:
            if kind == "group":
                if not is_authorized_telegram_group(destination):
                    return AuthorizationDecision(False, "chat Telegram fuera de la allowlist autorizada")
                if request.is_topic or request.thread_id is not None:
                    if not is_authorized_telegram_forum_route(
                        destination,
                        request.thread_id,
                    ):
                        return AuthorizationDecision(
                            False,
                            "topic Telegram fuera de AUTHORIZED_FORUM_ID",
                        )
                return AuthorizationDecision(True, "grupo y topic Telegram autorizados")
            if kind == "admin_private":
                if not is_authorized_admin_destination(destination):
                    return AuthorizationDecision(False, "destino administrativo Telegram no autorizado")
                return AuthorizationDecision(True, "destino administrativo Telegram autorizado")
            return AuthorizationDecision(False, "la acción requiere un destino Telegram autorizado")

        if platform == self.DISCORD and kind == "guild":
            if not self.is_authorized_discord_guild(destination):
                return AuthorizationDecision(False, "guild Discord fuera de la allowlist autorizada")
            return AuthorizationDecision(True, "guild Discord autorizada")

        return AuthorizationDecision(False, "plataforma o destino no autorizado")

    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Decide allow/deny sin ejecutar la acción ni tocar secretos."""
        platform = request.platform.strip().casefold()
        if platform not in {self.TELEGRAM, self.DISCORD}:
            return AuthorizationDecision(False, "plataforma no soportada")
        user_id = str(request.user_id).strip()
        if not user_id:
            return AuthorizationDecision(False, "identidad vacía")

        if request.requires_admin and not self.is_admin(platform, user_id):
            return AuthorizationDecision(False, "identidad sin permiso administrativo", permission="admin")

        if request.require_authorized_destination:
            destination = self._authorize_destination(request)
            if not destination.allowed:
                return AuthorizationDecision(
                    False,
                    destination.reason,
                    permission="admin" if request.requires_admin else "public",
                )

        return AuthorizationDecision(
            True,
            "identidad, plataforma y destino autorizados",
            permission="admin" if request.requires_admin else "public",
        )

    def authorize_telegram_admin(
        self,
        user_id: str,
        *,
        action: str,
        destination_id: str = "",
        destination_kind: str = "dm",
        thread_id: int | None = None,
        is_topic: bool = False,
        require_destination: bool = False,
    ) -> AuthorizationDecision:
        return self.authorize(
            AuthorizationRequest(
                self.TELEGRAM,
                str(user_id),
                action,
                destination_id=destination_id,
                destination_kind=destination_kind,
                thread_id=thread_id,
                is_topic=is_topic,
                requires_admin=True,
                require_authorized_destination=require_destination,
            )
        )

    def authorize_discord_event(
        self,
        user_id: str,
        *,
        action: str,
        guild_id: str,
        requires_admin: bool = False,
    ) -> AuthorizationDecision:
        return self.authorize(
            AuthorizationRequest(
                self.DISCORD,
                str(user_id),
                action,
                destination_id=str(guild_id),
                destination_kind="guild",
                requires_admin=requires_admin,
                require_authorized_destination=True,
            )
        )


def is_telegram_superadmin(user_id: str) -> bool:
    return AuthorityCore().is_superadmin(AuthorityCore.TELEGRAM, user_id)


def is_discord_superadmin(user_id: str) -> bool:
    return AuthorityCore().is_superadmin(AuthorityCore.DISCORD, user_id)


__all__ = [
    "AuthorizationDecision",
    "AuthorizationRequest",
    "AuthorityCore",
    "is_discord_superadmin",
    "is_telegram_superadmin",
]
