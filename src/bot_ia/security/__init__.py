# -*- coding: utf-8 -*-
"""Superficie de seguridad de BOT-IA."""

from .authority import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorityCore,
    is_discord_superadmin,
    is_telegram_superadmin,
)

__all__ = [
    "AuthorizationDecision",
    "AuthorizationRequest",
    "AuthorityCore",
    "is_discord_superadmin",
    "is_telegram_superadmin",
]
