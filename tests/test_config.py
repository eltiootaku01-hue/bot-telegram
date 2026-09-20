import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_world_timezone_has_cafe_default() -> None:
    settings = Settings()
    assert settings.bot_world_timezone == "America/Argentina/Buenos_Aires"


def test_world_timezone_is_trimmed() -> None:
    settings = Settings(bot_world_timezone="  Europe/Madrid  ")
    assert settings.bot_world_timezone == "Europe/Madrid"


def test_world_timezone_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        Settings(bot_world_timezone="   ")


def test_world_timezone_rejects_unknown_iana_value() -> None:
    with pytest.raises(ValidationError):
        Settings(bot_world_timezone="Mars/NoSuchCity")


def test_media_vault_channel_is_authorized_only_by_explicit_vault_id() -> None:
    settings = Settings(media_storage_chat_id=-100555)
    assert settings.is_chat_allowed(-100555, "channel") is True
    assert settings.is_chat_allowed(-100777, "channel") is False
    assert settings.is_chat_allowed(-100555, "supergroup") is False


def test_zero_media_vault_id_does_not_authorize_any_channel() -> None:
    settings = Settings(media_storage_chat_id=0)
    assert settings.is_chat_allowed(-100555, "channel") is False


def test_ai_curator_auto_is_disabled_by_default() -> None:
    settings = Settings()
    assert settings.ai_curator_auto is False
