from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class TmaAuthError(ValueError):
    """Raised when Telegram Mini App initData is invalid or stale."""


@dataclass(frozen=True, slots=True)
class TmaUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool = False


@dataclass(frozen=True, slots=True)
class TmaAuthContext:
    user: TmaUser
    auth_date: int
    query_id: str | None
    start_param: str | None
    raw_init_data: str


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 3600,
    now: int | None = None,
    future_skew_seconds: int = 60,
) -> TmaAuthContext:
    """Validate Telegram WebApp initData with the bot-token HMAC contract."""
    if not init_data or not init_data.strip():
        raise TmaAuthError("initData is required")
    if not bot_token:
        raise TmaAuthError("TMA bot token is not configured")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise TmaAuthError("initData has invalid query-string syntax") from exc

    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise TmaAuthError(f"Duplicate initData field: {key}")
        values[key] = value

    received_hash = values.pop("hash", "")
    # The bot-token hash covers every received field except the hash itself.
    # Telegram also exposes ``signature`` for third-party verification; it stays
    # in this data-check-string when the backend validates the bot HMAC.

    if not received_hash:
        raise TmaAuthError("initData hash is missing")
    if len(received_hash) != 64:
        raise TmaAuthError("initData hash has invalid length")
    try:
        int(received_hash, 16)
    except ValueError as exc:
        raise TmaAuthError("initData hash is not hexadecimal") from exc

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash.casefold()):
        raise TmaAuthError("initData HMAC verification failed")

    try:
        auth_date = int(values["auth_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TmaAuthError("auth_date is required and must be an integer") from exc

    current_time = int(time.time()) if now is None else int(now)
    age = current_time - auth_date
    if age > max_age_seconds:
        raise TmaAuthError("initData has expired")
    if age < -future_skew_seconds:
        raise TmaAuthError("initData auth_date is too far in the future")

    raw_user = values.get("user")
    if not raw_user:
        raise TmaAuthError("initData user is missing")
    try:
        payload = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise TmaAuthError("initData user is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TmaAuthError("initData user must be a JSON object")

    try:
        user_id = int(payload["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TmaAuthError("initData user.id is invalid") from exc
    if user_id <= 0:
        raise TmaAuthError("initData user.id must be positive")

    first_name = str(payload.get("first_name") or "").strip() or "Telegram user"
    return TmaAuthContext(
        user=TmaUser(
            id=user_id,
            first_name=first_name,
            last_name=str(payload["last_name"]) if payload.get("last_name") else None,
            username=str(payload["username"]) if payload.get("username") else None,
            language_code=(
                str(payload["language_code"]) if payload.get("language_code") else None
            ),
            is_premium=bool(payload.get("is_premium", False)),
        ),
        auth_date=auth_date,
        query_id=values.get("query_id"),
        start_param=values.get("start_param"),
        raw_init_data=init_data,
    )


def init_data_from_request(request) -> str:
    """Read the TMA credential from the custom header or Authorization scheme."""
    value = request.headers.get("X-Telegram-Init-Data", "")
    if value and value.strip():
        return value.strip()
    authorization = request.headers.get("Authorization", "")
    if authorization.casefold().startswith("tma "):
        return authorization[4:].strip()
    return ""
