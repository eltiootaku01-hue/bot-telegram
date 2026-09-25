# -*- coding: utf-8 -*-
"""Comprobaciones no bloqueantes de conectividad para el dashboard."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class PlatformHealth:
    platform: str
    ok: bool
    detail: str


def _probe(url: str, token: str) -> tuple[bool, str]:
    if not token.strip():
        return False, "token no configurado"
    request = Request(
        url,
        headers={"Authorization": f"Bot {token.strip()}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            raw = response.read(32 * 1024)
        value = json.loads(raw.decode("utf-8"))
    except HTTPError as error:
        return False, f"HTTP {error.code}"
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "sin conexión"
    if isinstance(value, dict) and value.get("id"):
        return True, "conectado"
    return False, "respuesta no válida"


def probe_telegram() -> PlatformHealth:
    ok, detail = _probe(
        "https://api.telegram.org/bot" + os.getenv("TELEGRAM_BOT_TOKEN", "") + "/getMe",
        os.getenv("TELEGRAM_BOT_TOKEN", ""),
    )
    return PlatformHealth("Telegram", ok, detail)


def probe_discord() -> PlatformHealth:
    ok, detail = _probe(
        "https://discord.com/api/v10/users/@me",
        os.getenv("DISCORD_BOT_TOKEN", ""),
    )
    return PlatformHealth("Discord", ok, detail)
