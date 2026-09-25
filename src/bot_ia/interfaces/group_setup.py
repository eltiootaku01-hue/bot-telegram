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
    ("#general", "general"),
    ("#tcg-collection", "tcg_collection"),
    ("#pedidos-sfw", "pedidos_sfw"),
    ("#noticias-otaku", "noticias_otaku"),
    ("#cantina-18", "cantina_18"),
    ("#pedidos-nsfw", "pedidos_nsfw"),
    ("#mesa-de-apuestas-21", "mesa_apuestas_21"),
    ("#pedidos", "pedidos"),
    ("#pedidos-admin", "pedidos_admin"),
    ("#atencion-y-quejas", "atencion_quejas"),
)

REPOST_FEEDS = (
    ("📢 Publicaciones", "https://t.me/eltiootaku"),
    ("🔞 Reposteo Yandere NSFW", "https://t.me/yandere_nsfw"),
    ("🎨 Reposteo Danbooru SFW", "https://t.me/danbooru_sfw"),
    ("🔞 Reposteo Danbooru NSFW", "https://t.me/danbooru_nsfw"),
)

SFW_ROOM_KEYS = frozenset({"general", "tcg_collection", "pedidos_sfw", "noticias_otaku"})
MATURE_ROOM_KEYS = frozenset({"cantina_18", "pedidos_nsfw", "mesa_apuestas_21"})
ADMIN_ROOM_KEY = "pedidos_admin"
ORDERS_ROOM_KEY = "pedidos"

# Telegram: en un grupo/supergrupo el bot puede aplicar permisos de envío.
# Discord: se traduce a permission overwrites para @everyone/bot/admin.
READ_ONLY_ORDERS = {
    "telegram": {"can_send_messages": False, "can_send_media": False},
    "discord": {"view_channel": True, "send_messages": False, "attach_files": False},
}



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

    def save_target(
        self,
        platform: str,
        target_id: str,
        rooms: tuple[GroupRoom, ...],
        *,
        feeds: tuple[tuple[str, str], ...] = REPOST_FEEDS,
    ) -> None:
        payload = self.load()
        payload[f"{platform}:{target_id}"] = {
            "rooms": [{"name": r.name, "key": r.key, "external_id": r.external_id} for r in rooms],
            "feeds": [{"name": name, "url": url} for name, url in feeds],
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def get_feeds(self, platform: str, target_id: str) -> tuple[tuple[str, str], ...]:
        raw = self.load().get(f"{platform}:{target_id}", {})
        items = raw.get("feeds", []) if isinstance(raw, dict) else []
        return tuple(
            (str(x["name"]), str(x["url"]))
            for x in items
            if isinstance(x, dict) and x.get("name") and x.get("url")
        )

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

    def delete_message(self, channel_id: str, message_id: str) -> None:
        self._request("DELETE", f"/channels/{channel_id}/messages/{message_id}")

    def ban_member(self, guild_id: str, user_id: str, *, delete_message_seconds: int = 604800) -> None:
        self._request(
            "PUT",
            f"/guilds/{guild_id}/bans/{user_id}",
            {"delete_message_seconds": max(0, min(int(delete_message_seconds), 604800))},
        )

    def timeout_member(self, guild_id: str, user_id: str, until_iso8601: str) -> None:
        self._request(
            "PATCH",
            f"/guilds/{guild_id}/members/{user_id}",
            {"communication_disabled_until": until_iso8601},
        )

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
            payload: dict[str, object] = {
                "name": name.lstrip("#"),
                "type": 0,
                "topic": f"BOT-IA · {key}",
            }
            if key == ADMIN_ROOM_KEY:
                # Discord permite hacer #pedidos privado mediante permission overwrites.
                overwrites = [
                    {"id": guild_id, "type": 0, "deny": str(1 << 10)},
                ]
                for role in roles:
                    if not isinstance(role, dict):
                        continue
                    try:
                        role_permissions = int(role.get("permissions", 0))
                    except (TypeError, ValueError):
                        continue
                    if role_permissions & 0x8:
                        overwrites.append(
                            {"id": str(role.get("id")), "type": 0, "allow": str((1 << 10) | (1 << 11))}
                        )
                for role_id in role_ids:
                    overwrites.append(
                        {"id": role_id, "type": 0, "allow": str((1 << 10) | (1 << 11))}
                    )
                payload["permission_overwrites"] = overwrites
            created = self._request(
                "POST",
                f"/guilds/{guild_id}/channels",
                payload,
            )
            if not isinstance(created, dict) or not created.get("id"):
                raise GroupSetupError(f"Discord no devolvió ID para {name}")
            room = GroupRoom(name, key, str(created["id"]))
            rooms.append(room)
            existing[key] = room
        result = GroupSetupResult("discord", guild_id, tuple(rooms))
        store.save_target("discord", guild_id, result.rooms)
        return result


class TelegramGroupSetup:
    """Provisiona temas de un supergrupo-foro usando el Bot API oficial."""

    API = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, *, timeout: float = 15.0) -> None:
        if not token.strip():
            raise GroupSetupError("TELEGRAM_BOT_TOKEN no está configurado")
        self.token = token.strip()
        self.timeout = timeout

    def _call(self, method: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            self.API.format(token=self.token, method=method),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise GroupSetupError(f"Telegram rechazó la operación HTTP {error.code}") from error
            raise GroupSetupError(f"Telegram HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise GroupSetupError("No se pudo contactar con Telegram") from error
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GroupSetupError("Telegram devolvió una respuesta inválida") from error
        if not isinstance(value, dict) or value.get("ok") is not True:
            description = value.get("description", "operación rechazada") if isinstance(value, dict) else "respuesta inválida"
            raise GroupSetupError(f"Telegram: {description}")
        return value

    def setup_chat(self, chat_id: str, store: GroupSetupStore) -> GroupSetupResult:
        chat_id = str(chat_id).strip()
        if not chat_id:
            raise GroupSetupError("chat_id es obligatorio")
        me = self._call("getMe", {})
        bot_id = me.get("result", {}).get("id") if isinstance(me.get("result"), dict) else None
        if not isinstance(bot_id, int):
            raise GroupSetupError("No se pudo identificar al bot de Telegram")
        member = self._call("getChatMember", {"chat_id": chat_id, "user_id": bot_id})
        member_data = member.get("result")
        if not isinstance(member_data, dict) or member_data.get("status") not in {"administrator", "creator"}:
            raise GroupSetupError("El bot de Telegram debe ser administrador del grupo")
        if member_data.get("status") == "administrator" and not member_data.get("can_manage_topics", False):
            raise GroupSetupError("El bot necesita el permiso can_manage_topics")
        chat = self._call("getChat", {"chat_id": chat_id})
        chat_data = chat.get("result")
        if not isinstance(chat_data, dict) or not chat_data.get("is_forum", False):
            raise GroupSetupError("El grupo de Telegram debe ser un supergrupo con Temas/Foro activado")

        existing = {r.key: r for r in store.get_rooms("telegram", chat_id)}
        rooms: list[GroupRoom] = list(existing.values())
        for name, key in ROOMS:
            if key in existing:
                continue
            created = self._call("createForumTopic", {"chat_id": chat_id, "name": name})
            topic = created.get("result")
            topic_id = topic.get("message_thread_id") if isinstance(topic, dict) else None
            if not isinstance(topic_id, int):
                raise GroupSetupError(f"Telegram no devolvió ID para {name}")
            room = GroupRoom(name, key, str(topic_id))
            rooms.append(room)
            existing[key] = room
        result = GroupSetupResult("telegram", chat_id, tuple(rooms))
        store.save_target("telegram", chat_id, result.rooms)
        return result


class DiscordSetupCommand:
    """Handler desacoplado para conectar /setup_group a cualquier runtime Discord."""

    def __init__(self, root: Path) -> None:
        self.store = GroupSetupStore(root)

    def handle_setup_group(self, guild_id: str) -> str:
        try:
            result = DiscordGroupSetup(os.getenv("DISCORD_BOT_TOKEN", "")).setup_guild(
                guild_id,
                self.store,
            )
        except GroupSetupError as error:
            return f"No se pudo estructurar Discord: {error}"
        feeds = self.store.get_feeds("discord", guild_id)
        return (
            "Estructura Discord preparada:\n"
            + "\n".join(f"• {room.name} → canal {room.external_id}" for room in result.rooms)
            + "\n\nFeeds configurados:\n"
            + "\n".join(f"• {name}: {url}" for name, url in feeds)
        )
