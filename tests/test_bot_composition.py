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
            {"system", "social_runtime", "chat", "moderation", "brain_chat"},
        ),
        (
            BotIdentity.SUNNA,
            {"system", "social_runtime", "chat", "game", "trivia", "media", "admin", "brain_chat"},
        ),
        (
            BotIdentity.CAMI,
            {"system", "social_runtime", "chat", "cami-media", "cami-media-publisher", "admin", "brain_chat"},
        ),
        (
            BotIdentity.CHIE,
            {"system", "social_runtime", "chat", "chie", "requests", "brain_chat"},
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

    cari_modules = build_bot_modules(database, BotIdentity.CARI, settings)
    brain = next(module for module in cari_modules if module.name == "brain_chat")
    social = next(module for module in cari_modules if module.name == "social_runtime")
    assert brain.settings is settings
    assert social.runtime.settings is settings

    sunna_modules = build_bot_modules(database, BotIdentity.SUNNA, settings)
    trivia = next(module for module in sunna_modules if module.name == "trivia")
    media = next(module for module in sunna_modules if module.name == "media")
    assert trivia.settings is settings
    assert media.settings is settings

    cami_modules = build_bot_modules(database, BotIdentity.CAMI, settings)
    cami_media = next(module for module in cami_modules if module.name == "cami-media")
    publisher = next(module for module in cami_modules if module.name == "cami-media-publisher")
    assert cami_media.settings is settings
    assert publisher.settings is settings

    chie_modules = build_bot_modules(database, BotIdentity.CHIE, settings)
    chie = next(module for module in chie_modules if module.name == "chie")
    assert chie.settings is settings
