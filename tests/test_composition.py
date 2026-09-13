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
