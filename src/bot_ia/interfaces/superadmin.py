# -*- coding: utf-8 -*-
"""Identidad de SuperAdmin para excepciones de sanción."""

from __future__ import annotations

import os


SUPERADMIN_USERNAME = "tiootakuu"
SUPERADMIN_TELEGRAM_URL = "https://t.me/tiootakuu"


def is_superadmin(user_id: str = "", username: str = "") -> bool:
    configured_id = os.getenv("DISCORD_SUPERADMIN_USER_ID", "").strip()
    configured_username = os.getenv("TELEGRAM_SUPERADMIN_USERNAME", SUPERADMIN_USERNAME).strip().lstrip("@").casefold()
    return (
        bool(configured_id) and str(user_id).strip() == configured_id
    ) or str(username).strip().lstrip("@").casefold() == configured_username
