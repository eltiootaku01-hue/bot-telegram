from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from app.core.identity import BotIdentity
from app.core.module import BotModule


ModuleFactory = Callable[[], BotModule]


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """Reusable module definition used to compose one bot identity."""

    name: str
    factory: ModuleFactory
    identities: frozenset[BotIdentity] = frozenset()
    optional: bool = False

    def supports(self, identity: BotIdentity) -> bool:
        return not self.identities or identity in self.identities


class BotComposition:
    """Build a bot from reusable module specifications.

    Composition is deterministic: specifications keep their declared order and
    only modules compatible with the selected identity are instantiated. The
    composition layer knows nothing about AI, cloud APIs, or network services.
    """

    def __init__(self, specs: Iterable[ModuleSpec]) -> None:
        self._specs = tuple(specs)
        self._validate_specs()

    def build(self, identity: BotIdentity) -> list[BotModule]:
        modules: list[BotModule] = []
        for spec in self._specs:
            if spec.supports(identity):
                modules.append(spec.factory())
        return modules

    def _validate_specs(self) -> None:
        names: set[str] = set()
        for spec in self._specs:
            if not spec.name.strip():
                raise ValueError("module specification name must not be empty")
            if spec.name in names:
                raise ValueError(f"duplicate module specification: {spec.name}")
            names.add(spec.name)


def default_composition(
    shared: dict[str, ModuleFactory],
    per_identity: dict[BotIdentity, tuple[ModuleSpec, ...]],
) -> BotComposition:
    """Combine shared modules with identity-specific reusable specifications."""

    specs = [
        ModuleSpec(name, factory)
        for name, factory in shared.items()
    ]
    for identity_specs in per_identity.values():
        specs.extend(identity_specs)
    return BotComposition(specs)
