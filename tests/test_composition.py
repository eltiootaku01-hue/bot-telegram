from __future__ import annotations

import pytest

from app.core.composition import BotComposition, ModuleSpec
from app.core.identity import BotIdentity
from app.core.module import BotModule


class DemoModule(BotModule):
    name = "demo"

    def setup(self) -> None:
        pass


def test_composition_preserves_declared_order_and_filters_identity() -> None:
    specs = (
        ModuleSpec("shared", DemoModule),
        ModuleSpec("cari-only", DemoModule, frozenset({BotIdentity.CARI})),
        ModuleSpec("sunna-only", DemoModule, frozenset({BotIdentity.SUNNA})),
    )
    modules = BotComposition(specs).build(BotIdentity.CARI)

    assert [module.name for module in modules] == ["demo", "demo"]


def test_empty_identity_set_is_shared() -> None:
    spec = ModuleSpec("shared", DemoModule)
    assert spec.supports(BotIdentity.CAMI)


def test_duplicate_specification_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate module specification"):
        BotComposition((ModuleSpec("x", DemoModule), ModuleSpec("x", DemoModule)))


def test_empty_specification_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        BotComposition((ModuleSpec(" ", DemoModule),))


def test_product_game_ownership_is_explicit() -> None:
    from app.core.bot_composition import build_bot_modules
    from app.core.config import Settings
    from app.db.database import Database

    database = Database("sqlite+aiosqlite:///:memory:")
    settings = Settings(authorized_chat_ids="-100")

    cari = {module.name for module in build_bot_modules(database, BotIdentity.CARI, settings)}
    sunna = {module.name for module in build_bot_modules(database, BotIdentity.SUNNA, settings)}
    cami = {module.name for module in build_bot_modules(database, BotIdentity.CAMI, settings)}
    chie = {module.name for module in build_bot_modules(database, BotIdentity.CHIE, settings)}

    assert "trivia" in cari
    assert "game" not in cari
    assert "game" in sunna
    assert "trivia" not in sunna
    assert "mystery" in cami
    assert "trivia" not in cami
    assert "chie" in chie
    assert "mystery" not in chie
