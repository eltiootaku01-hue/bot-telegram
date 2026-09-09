"""Punto de construcción del runtime de BOT-IA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot_ia.config import (
    RuntimeConfig,
    RuntimeRegistry,
    load_default_runtime_config,
)
from bot_ia.contracts import UniverseDefinition, UniverseRegistry
from bot_ia.core.application import (
    BotApplication,
    InMemorySessionStore,
)
from bot_ia.core.brain import LocalBrain
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.core.router import Router
from bot_ia.librarian import EntityIndex, SourceInventory
from bot_ia.librarian.models import CatalogEntry
from bot_ia.providers import ProviderManager, build_provider_manager


@dataclass(frozen=True, slots=True)
class UniverseRuntime:
    definition: UniverseDefinition
    entries: tuple[CatalogEntry, ...]
    entity_index: EntityIndex


@dataclass(frozen=True, slots=True)
class RuntimeComponents:
    config: RuntimeConfig
    registry: RuntimeRegistry
    universe_registry: UniverseRegistry
    universes: tuple[UniverseRuntime, ...]
    provider_manager: ProviderManager

    def universe(self, universe_id: str) -> UniverseRuntime:
        for universe in self.universes:
            if universe.definition.universe_id == universe_id:
                return universe

        raise KeyError(f"universe not configured: {universe_id}")

    def build_application(
        self,
        *,
        default_universe_id: str | None = None,
        provider_id: str = "ollama",
    ) -> BotApplication:
        provider_config = self.registry.provider(provider_id)

        entries_by_universe = {
            universe.definition.universe_id: universe.entries
            for universe in self.universes
        }

        entity_indexes_by_universe = {
            universe.definition.universe_id: universe.entity_index
            for universe in self.universes
        }

        def candidate_provider(
            universe_id: str,
        ) -> tuple:
            return self.universe(universe_id).entity_index.for_universe(
                universe_id
            )

        workflow = LocalWorkflow(
            entries_by_universe,
            entity_indexes=entity_indexes_by_universe,
            provider_manager=self.provider_manager,
            provider_config=provider_config,
        )

        return BotApplication(
            LocalBrain(self.universe_registry),
            Router(),
            InMemorySessionStore(),
            default_universe_id=default_universe_id,
            candidate_provider=candidate_provider,
            executor=workflow,
        )


def _build_universe_runtime(
    config: RuntimeConfig,
) -> tuple[UniverseRegistry, tuple[UniverseRuntime, ...]]:
    registry = UniverseRegistry()
    universes: list[UniverseRuntime] = []

    for universe in config.universes:
        definition = UniverseDefinition(
            universe_id=universe.universe_id,
            display_name=universe.display_name,
            root_path=universe.root_path,
            spoiler_policy=universe.spoiler_policy,
            language=universe.language,
        )

        registry.register(definition)

        inventory = SourceInventory(definition.root_path)
        entries = inventory.discover(definition.universe_id)
        entity_index = EntityIndex(entries)

        universes.append(
            UniverseRuntime(
                definition=definition,
                entries=entries,
                entity_index=entity_index,
            )
        )

    return registry, tuple(universes)


def build_runtime(
    project_root: Path,
    *,
    key_loader=None,
    transports=None,
) -> RuntimeComponents:
    config = load_default_runtime_config(project_root)

    registry = RuntimeRegistry(config)
    universe_registry, universes = _build_universe_runtime(config)

    provider_manager = build_provider_manager(
        config,
        key_loader=key_loader,
        transports=transports,
    )

    return RuntimeComponents(
        config=config,
        registry=registry,
        universe_registry=universe_registry,
        universes=universes,
        provider_manager=provider_manager,
    )


