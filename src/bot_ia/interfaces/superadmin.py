# -*- coding: utf-8 -*-
"""Identidad de SuperAdmin para excepciones de sanción."""

from __future__ import annotations

from bot_ia.security.authority import AuthorityCore


SUPERADMIN_USERNAME = "tiootakuu"
SUPERADMIN_TELEGRAM_URL = "https://t.me/tiootakuu"


def is_superadmin(user_id: str = "", username: str = "") -> bool:
    """Compatibilidad; la confianza depende sólo de IDs estables."""
    authority = AuthorityCore()
    uid = str(user_id).strip()
    return (
        authority.is_superadmin(AuthorityCore.TELEGRAM, uid)
        or authority.is_superadmin(AuthorityCore.DISCORD, uid)
    )
