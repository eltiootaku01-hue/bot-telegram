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
