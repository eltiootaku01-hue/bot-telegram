# -*- coding: utf-8 -*-
"""Validación server-side de Telegram Mini App initData."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Mapping
from urllib.parse import parse_qsl

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_AUTH_MAX_AGE_SECONDS = 3600
DEFAULT_AUTH_FUTURE_TOLERANCE_SECONDS = 30
MAX_INIT_DATA_FIELDS = 128
AUTH_HEADER_SCHEME = "tma"


class TelegramAuthError(ValueError):
    """Error seguro de validación; no contiene secretos ni initData crudo."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AuthenticatedTelegramActor(BaseModel):
    """Identidad derivada exclusivamente de initData verificado."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    telegram_user_id: int = Field(gt=0)
    actor_key: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    auth_date: int = Field(gt=0)
    chat_instance: str | None = None
    chat_type: str | None = None
    start_param: str | None = None

    @property
    def id(self) -> int:
        return self.telegram_user_id


TelegramUserData = AuthenticatedTelegramActor


def _configured_seconds(
    name: str,
    default: int,
    *,
    minimum: int = 0,
) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise TelegramAuthError("invalid_configuration") from error
    if value < minimum:
        raise TelegramAuthError("invalid_configuration")
    return value


def _parse_timestamp(value: str) -> int:
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as error:
        raise TelegramAuthError("invalid_auth_date") from error
    if timestamp <= 0:
        raise TelegramAuthError("invalid_auth_date")
    return timestamp


def _parse_user(raw_value: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw_value)
    except (TypeError, ValueError) as error:
        raise TelegramAuthError("invalid_user_json") from error
    if not isinstance(value, dict):
        raise TelegramAuthError("invalid_user_json")

    raw_id = value.get("id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
        raise TelegramAuthError("invalid_user_id")
    return value


def extract_tma_init_data(authorization_header: str | None) -> str:
    """Acepta únicamente Authorization: tma <raw initData>."""
    if not authorization_header:
        raise TelegramAuthError("missing_authorization")

    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].casefold() != AUTH_HEADER_SCHEME:
        raise TelegramAuthError("invalid_authorization_scheme")
    if not parts[1].strip():
        raise TelegramAuthError("missing_init_data")
    return parts[1]


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: float | None = None,
    max_age_seconds: int | None = None,
    future_tolerance_seconds: int | None = None,
) -> AuthenticatedTelegramActor:
    """Verifica initData siguiendo el algoritmo de Telegram Mini Apps."""
    if not isinstance(init_data, str) or not init_data.strip():
        raise TelegramAuthError("missing_init_data")
    if not isinstance(bot_token, str) or not bot_token.strip():
        raise TelegramAuthError("missing_bot_token")

    try:
        pairs = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=MAX_INIT_DATA_FIELDS,
        )
    except ValueError as error:
        raise TelegramAuthError("malformed_init_data") from error

    fields: dict[str, str] = {}
    for key, value in pairs:
        if not key or key in fields:
            raise TelegramAuthError("duplicate_or_empty_field")
        fields[key] = value

    received_hash = fields.get("hash", "")
    if len(received_hash) != 64:
        raise TelegramAuthError("invalid_hash")
    try:
        expected_hash_bytes = bytes.fromhex(received_hash)
    except ValueError as error:
        raise TelegramAuthError("invalid_hash") from error

    data_check_string = "\n".join(
        f"{key}={fields[key]}"
        for key in sorted(fields)
        if key != "hash"
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(expected_hash_bytes, calculated_hash):
        raise TelegramAuthError("invalid_hash")

    auth_date = _parse_timestamp(fields.get("auth_date", ""))
    current_time = time.time() if now is None else float(now)

    max_age = (
        _configured_seconds(
            "TMA_AUTH_MAX_AGE_SECONDS",
            DEFAULT_AUTH_MAX_AGE_SECONDS,
            minimum=1,
        )
        if max_age_seconds is None
        else int(max_age_seconds)
    )
    future_tolerance = (
        _configured_seconds(
            "TMA_AUTH_FUTURE_TOLERANCE_SECONDS",
            DEFAULT_AUTH_FUTURE_TOLERANCE_SECONDS,
            minimum=0,
        )
        if future_tolerance_seconds is None
        else int(future_tolerance_seconds)
    )

    if max_age < 1 or future_tolerance < 0:
        raise TelegramAuthError("invalid_configuration")
    if auth_date > current_time + future_tolerance:
        raise TelegramAuthError("future_auth_date")
    if current_time - auth_date > max_age:
        raise TelegramAuthError("expired_auth_date")

    if "user" not in fields or not fields["user"]:
        raise TelegramAuthError("missing_user")
    user = _parse_user(fields["user"])

    telegram_user_id = int(user["id"])
    username = user.get("username")
    first_name = user.get("first_name")
    last_name = user.get("last_name")

    for name, value in (
        ("username", username),
        ("first_name", first_name),
        ("last_name", last_name),
    ):
        if value is not None and not isinstance(value, str):
            raise TelegramAuthError(f"invalid_{name}")

    return AuthenticatedTelegramActor(
        telegram_user_id=telegram_user_id,
        actor_key=f"telegram:{telegram_user_id}",
        username=username,
        first_name=first_name,
        last_name=last_name,
        auth_date=auth_date,
        chat_instance=fields.get("chat_instance") or None,
        chat_type=fields.get("chat_type") or None,
        start_param=fields.get("start_param") or None,
    )


__all__ = [
    "AUTH_HEADER_SCHEME",
    "AuthenticatedTelegramActor",
    "DEFAULT_AUTH_FUTURE_TOLERANCE_SECONDS",
    "DEFAULT_AUTH_MAX_AGE_SECONDS",
    "MAX_INIT_DATA_FIELDS",
    "TelegramAuthError",
    "TelegramUserData",
    "extract_tma_init_data",
    "validate_telegram_init_data",
]
