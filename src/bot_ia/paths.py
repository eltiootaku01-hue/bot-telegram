# -*- coding: utf-8 -*-
"""Rutas persistentes únicas de BOT-IA."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _resolve_project_root() -> Path:
    configured = os.getenv("BOT_IA_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _resolve_project_root()
CONFIG_DIR = PROJECT_ROOT / "config"
ECONOMY_DB_PATH = CONFIG_DIR / "bot_ia_economy.sqlite3"
