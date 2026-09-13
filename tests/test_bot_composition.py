from __future__ import annotations

import pytest

from app.core.bot_composition import build_bot_modules
from app.core.config import Settings
from app.core.identity import BotIdentity
from app.db.database import Database


@pytest.mark.parametrize(
    ("identity", "expected"),
    (
        (
            BotIdentity.CARI,
            {"system", "social_runtime", "chat", "brain_chat"},
        ),
        (
            BotIdentity.SUNNA,
            {"system", "social_runtime", "game", "trivia", "media", "admin", "brain_chat"},
        ),
        (
            BotIdentity.CAMI,
            {"system", "social_runtime", "cami-media", "cami-media-publisher", "admin", "brain_chat"},
        ),
        (
            BotIdentity.CHIE,
            {"system", "social_runtime", "chie", "requests", "brain_chat"},
        ),
    ),
)
def test_each_identity_gets_expected_module_set(identity: BotIdentity, expected: set[str]) -> None:
    settings = Settings(ai_enabled=False)
    database = Database("sqlite+aiosqlite:///:memory:")
    modules = build_bot_modules(database, identity, settings)
    names = {module.name for module in modules}
    assert names == expected


def test_composition_uses_supplied_settings_instance() -> None:
    settings = Settings(ai_enabled=False)
    database = Database("sqlite+aiosqlite:///:memory:")
    modules = build_bot_modules(database, BotIdentity.CARI, settings)
    brain = next(module for module in modules if module.name == "brain_chat")
    social = next(module for module in modules if module.name == "social_runtime")
    assert brain.settings is settings
    assert social.runtime.settings is settings
