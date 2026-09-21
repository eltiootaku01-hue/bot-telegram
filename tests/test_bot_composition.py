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
            {"system", "world-catalog", "world-runtime", "social_runtime", "chat", "cafe", "moderation", "trivia", "story", "brain_chat", "tio-operator"},
        ),
        (
            BotIdentity.SUNNA,
            {"system", "world-catalog", "world-runtime", "social_runtime", "chat", "game", "media", "admin", "brain_chat"},
        ),
        (
            BotIdentity.CAMI,
            {"system", "world-catalog", "world-runtime", "social_runtime", "chat", "cami-media", "cami-media-publisher", "mystery", "brain_chat"},
        ),
        (
            BotIdentity.CHIE,
            {"system", "world-catalog", "world-runtime", "social_runtime", "chat", "chie", "requests", "brain_chat"},
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
    media = next(module for module in sunna_modules if module.name == "media")
    assert media.settings is settings

    cami_modules = build_bot_modules(database, BotIdentity.CAMI, settings)

    cari_trivia = next(module for module in cari_modules if module.name == "trivia")
    assert cari_trivia.settings is settings

    cami_mystery = next(module for module in cami_modules if module.name == "mystery")
    assert cami_mystery.settings is settings

    cami_modules = build_bot_modules(database, BotIdentity.CAMI, settings)
    cami_media = next(module for module in cami_modules if module.name == "cami-media")
    publisher = next(module for module in cami_modules if module.name == "cami-media-publisher")
    assert cami_media.settings is settings
    assert publisher.settings is settings

    chie_modules = build_bot_modules(database, BotIdentity.CHIE, settings)
    chie = next(module for module in chie_modules if module.name == "chie")
    assert chie.settings is settings


def test_cari_cafe_module_receives_configured_world_timezone() -> None:
    from app.modules.cafe.module import CafeModule

    settings = Settings(bot_world_timezone="Europe/Madrid")
    database = Database("sqlite+aiosqlite:///:memory:")

    modules = build_bot_modules(database, BotIdentity.CARI, settings)
    cafe = next(module for module in modules if module.name == "cafe")

    assert isinstance(cafe, CafeModule)
    assert cafe.timezone_name == "Europe/Madrid"


def test_cami_does_not_mount_sunna_gacha_admin_module() -> None:
    settings = Settings(ai_enabled=False)
    database = Database("sqlite+aiosqlite:///:memory:")

    modules = build_bot_modules(database, BotIdentity.CAMI, settings)
    names = {module.name for module in modules}

    assert "admin" not in names
    assert "cami-admin" not in names


def test_cari_cafe_module_receives_cross_bot_links() -> None:
    from app.modules.cafe.module import CafeModule

    settings = Settings(
        bot_link_sunna="https://t.me/SunnaBot",
        bot_link_cami="https://t.me/CamiBot",
        bot_link_chie="https://t.me/ChieBot",
    )
    database = Database("sqlite+aiosqlite:///:memory:")

    modules = build_bot_modules(database, BotIdentity.CARI, settings)
    cafe = next(module for module in modules if module.name == "cafe")

    assert isinstance(cafe, CafeModule)
    assert cafe.settings is settings
