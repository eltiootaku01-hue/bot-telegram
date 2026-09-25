# -*- coding: utf-8 -*-
"""Políticas estrictas de autorización para grupos y administración de Telegram."""

from __future__ import annotations

import os


def _env_ids(*names: str) -> frozenset[str]:
    values: set[str] = set()
    for name in names:
        raw = os.getenv(name, "")
        values.update(
            value.strip()
            for value in raw.split(",")
            if value.strip()
        )
    return frozenset(values)


def authorized_group_ids() -> frozenset[str]:
    """Allowlist de chats oficiales; vacía significa fail-closed para grupos."""
    return _env_ids(
        "AUTHORIZED_GROUP_ID",
        "TELEGRAM_OFFICIAL_CHAT_IDS",
    )


def authorized_forum_routes() -> frozenset[tuple[str, int]]:
    """Allowlist exacta de pares chat_id:message_thread_id."""
    result: set[tuple[str, int]] = set()
    raw = os.getenv("AUTHORIZED_FORUM_ID", "")
    for value in raw.split(","):
        token = value.strip()
        if not token:
            continue
        if ":" not in token:
            continue
        chat_id, thread = token.rsplit(":", 1)
        chat_id = chat_id.strip()
        try:
            thread_id = int(thread.strip())
        except ValueError:
            continue
        if chat_id:
            result.add((chat_id, thread_id))
    return frozenset(result)


def is_authorized_telegram_group(
    chat_id: str,
    *,
    message_thread_id: int | None = None,
) -> bool:
    """Valida únicamente la pertenencia del chat a la allowlist oficial."""
    clean_chat = str(chat_id).strip()
    return bool(clean_chat and clean_chat in authorized_group_ids())


def is_authorized_telegram_forum_route(
    chat_id: str,
    message_thread_id: int | None,
) -> bool:
    """Valida un par chat/topic cuando AUTHORIZED_FORUM_ID fue configurado."""
    forums = authorized_forum_routes()
    if not forums:
        return True
    if message_thread_id is None:
        return False
    try:
        return (str(chat_id).strip(), int(message_thread_id)) in forums
    except (TypeError, ValueError):
        return False


def is_authorized_admin_destination(chat_id: str) -> bool:
    """Sólo acepta un destino marcado privado y distinto de grupos oficiales."""
    clean_chat = str(chat_id).strip()
    if not clean_chat:
        return False
    if os.getenv("TELEGRAM_ADMIN_CHAT_PRIVATE", "").strip().lower() not in {
        "1", "true", "yes", "on"
    }:
        return False
    return clean_chat not in authorized_group_ids()


def require_authorized_group(
    chat_id: str,
    *,
    message_thread_id: int | None = None,
) -> None:
    if not is_authorized_telegram_group(
        chat_id,
        message_thread_id=message_thread_id,
    ):
        raise PermissionError(
            "Destino Telegram fuera de la allowlist autorizada"
        )
