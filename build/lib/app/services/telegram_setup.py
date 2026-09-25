from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class TelegramBotIdentity:
    configured: bool
    ok: bool
    bot_id: int | None = None
    username: str = ""
    first_name: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class TelegramChatCheck:
    ok: bool
    chat_id: int
    title: str = ""
    chat_type: str = ""
    username: str = ""
    bot_status: str = ""
    is_admin: bool = False
    missing_rights: tuple[str, ...] = ()
    error: str = ""


ROLE_ADMIN_RIGHTS: dict[str, tuple[str, ...]] = {
    "cari": ("delete_messages", "restrict_members"),
    "sunna": (),
    "cami": (),
    "chie": ("delete_messages", "restrict_members", "manage_topics"),
}


def _api_call(token: str, method: str, params: dict[str, object] | None = None) -> dict:
    if not token.strip():
        raise ValueError("Telegram bot token is empty")
    query = urlencode(params or {})
    url = f"https://api.telegram.org/bot{token.strip()}/{method}"
    if query:
        url = f"{url}?{query}"
    request = Request(url, headers={"User-Agent": "BotTelegram-Manager/1.0"})
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from Telegram") from exc
    except URLError as exc:
        raise RuntimeError("Telegram API unreachable") from exc
    except (TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Invalid response from Telegram API") from exc
    if not payload.get("ok"):
        description = str(payload.get("description") or "Telegram API error")
        raise RuntimeError(description)
    return payload


def verify_bot_token(token: str) -> TelegramBotIdentity:
    if not token.strip():
        return TelegramBotIdentity(configured=False, ok=False, error="Token vacío")
    try:
        result = _api_call(token, "getMe")["result"]
    except Exception as exc:
        return TelegramBotIdentity(configured=True, ok=False, error=str(exc))
    return TelegramBotIdentity(
        configured=True,
        ok=True,
        bot_id=int(result["id"]),
        username=str(result.get("username") or ""),
        first_name=str(result.get("first_name") or ""),
    )


def check_bot_in_chat(
    token: str,
    chat_id: int,
    *,
    required_rights: tuple[str, ...] = (),
) -> TelegramChatCheck:
    try:
        chat = _api_call(token, "getChat", {"chat_id": chat_id})["result"]
        me = _api_call(token, "getMe")["result"]
        member = _api_call(
            token,
            "getChatMember",
            {"chat_id": chat_id, "user_id": int(me["id"])},
        )["result"]
    except Exception as exc:
        return TelegramChatCheck(ok=False, chat_id=chat_id, error=str(exc))

    status = str(member.get("status") or "")
    is_admin = status in {"administrator", "creator"}
    missing = tuple(
        right
        for right in required_rights
        if not bool(member.get(f"can_{right}", False))
    )
    ok = status not in {"left", "kicked", ""} and not missing
    return TelegramChatCheck(
        ok=ok,
        chat_id=chat_id,
        title=str(chat.get("title") or chat.get("first_name") or ""),
        chat_type=str(chat.get("type") or ""),
        username=str(chat.get("username") or ""),
        bot_status=status,
        is_admin=is_admin,
        missing_rights=missing,
    )


def build_group_add_link(username: str, *, role: str) -> str:
    clean = username.lstrip("@").strip()
    if not clean:
        raise ValueError("Bot username is required")
    permissions = ROLE_ADMIN_RIGHTS.get(role, ())
    params: list[tuple[str, str]] = [("startgroup", "bottelegram")]
    if permissions:
        params.append(("admin", "+".join(permissions)))
    return f"https://t.me/{clean}?{urlencode(params, safe='+')}"


def build_private_link(username: str) -> str:
    clean = username.lstrip("@").strip()
    if not clean:
        raise ValueError("Bot username is required")
    return f"https://t.me/{clean}"


def required_group_rights(role: str) -> tuple[str, ...]:
    return ROLE_ADMIN_RIGHTS.get(role, ())


def build_start_link(username: str, parameter: str) -> str:
    clean = username.lstrip("@").strip()
    parameter = parameter.strip()
    if not clean:
        raise ValueError("Bot username is required")
    if not parameter or not all(character.isalnum() or character in "_-" for character in parameter):
        raise ValueError("Start parameter must use only A-Z, a-z, 0-9, _ or -")
    if len(parameter) > 64:
        raise ValueError("Start parameter is too long")
    return f"https://t.me/{clean}?start={parameter}"
