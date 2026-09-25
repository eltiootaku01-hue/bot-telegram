# -*- coding: utf-8 -*-
"""Estructuración automática de grupos Telegram/Discord, con permisos y resultados idempotentes."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOMS = (
    ("📌 Anuncios / General", "announcements"),
    ("🎴 Colección TCG", "tcg"),
    ("🎮 Minijuegos (21 / UNO / PPT)", "games"),
    ("💬 Zona de Meseras", "waitresses"),
)


class GroupSetupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GroupRoom:
    name: str
    key: str
    external_id: str


@dataclass(frozen=True, slots=True)
class GroupSetupResult:
    platform: str
    target_id: str
    rooms: tuple[GroupRoom, ...]


class GroupSetupStore:
    """Persistencia local para no duplicar estructuras creadas por BOT-IA."""

    def __init__(self, root: Path) -> None:
        self.path = Path(root) / "config" / "group_setup.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, object]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def save_target(self, platform: str, target_id: str, rooms: tuple[GroupRoom, ...]) -> None:
        payload = self.load()
        payload[f"{platform}:{target_id}"] = {
            "rooms": [{"name": r.name, "key": r.key, "external_id": r.external_id} for r in rooms]
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def get_rooms(self, platform: str, target_id: str) -> tuple[GroupRoom, ...]:
        raw = self.load().get(f"{platform}:{target_id}", {})
        items = raw.get("rooms", []) if isinstance(raw, dict) else []
        return tuple(
            GroupRoom(str(x["name"]), str(x["key"]), str(x["external_id"]))
            for x in items
            if isinstance(x, dict) and x.get("name") and x.get("key") and x.get("external_id")
        )


class DiscordGroupSetup:
    """Cliente REST mínimo: no agrega una dependencia Discord sólo para provisionar canales."""

    API = "https://discord.com/api/v10"

    def __init__(self, token: str, *, timeout: float = 15.0) -> None:
        if not token.strip():
            raise GroupSetupError("DISCORD_BOT_TOKEN no está configurado")
        self.token = token.strip()
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object] | list[object]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.API}{path}",
            data=data,
            headers={"Authorization": f"Bot {self.token}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise GroupSetupError(f"Discord rechazó la operación HTTP {error.code}") from error
            raise GroupSetupError(f"Discord HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise GroupSetupError("No se pudo contactar con Discord") from error
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GroupSetupError("Discord devolvió una respuesta inválida") from error
        if not isinstance(value, (dict, list)):
            raise GroupSetupError("Respuesta Discord inválida")
        return value

    def setup_guild(self, guild_id: str, store: GroupSetupStore) -> GroupSetupResult:
        guild_id = str(guild_id).strip()
        if not guild_id:
            raise GroupSetupError("guild_id es obligatorio")
        me = self._request("GET", "/users/@me")
        if not isinstance(me, dict) or not me.get("id"):
            raise GroupSetupError("No se pudo identificar al bot de Discord")
        member = self._request("GET", f"/guilds/{guild_id}/members/{me['id']}")
        roles = self._request("GET", f"/guilds/{guild_id}/roles")
        if not isinstance(member, dict) or not isinstance(roles, list):
            raise GroupSetupError("No se pudo verificar la membresía del bot")
        role_ids = {str(x) for x in member.get("roles", [])}
        permissions = 0
        for role in roles:
            if isinstance(role, dict) and str(role.get("id")) in role_ids:
                try:
                    permissions |= int(role.get("permissions", 0))
                except (TypeError, ValueError):
                    pass
        if not (permissions & 0x8 or permissions & 0x10):
            raise GroupSetupError("El bot necesita Administrador o Gestionar Canales en Discord")

        existing = {r.key: r for r in store.get_rooms("discord", guild_id)}
        rooms: list[GroupRoom] = list(existing.values())
        for name, key in ROOMS:
            if key in existing:
                continue
            created = self._request(
                "POST",
                f"/guilds/{guild_id}/channels",
                {"name": name, "type": 0, "topic": f"BOT-IA · {key}"},
            )
            if not isinstance(created, dict) or not created.get("id"):
                raise GroupSetupError(f"Discord no devolvió ID para {name}")
            room = GroupRoom(name, key, str(created["id"]))
            rooms.append(room)
            existing[key] = room
        result = GroupSetupResult("discord", guild_id, tuple(rooms))
        store.save_target("discord", guild_id, result.rooms)
        return result
