# -*- coding: utf-8 -*-
"""Punto de construcción del runtime de BOT-IA."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading

from bot_ia.config import RuntimeConfig, RuntimeRegistry, load_default_runtime_config
from bot_ia.contracts import UniverseDefinition, UniverseRegistry
from bot_ia.core.application import BotApplication
from bot_ia.core.backup_service import BackupService, BackupSnapshot
from bot_ia.core.brain import LocalBrain
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.core.mama_mia_supervisor import MamaMiaSupervisor
from bot_ia.core.waitress_session_manager import WaitressSessionManager
from bot_ia.core.project_manager import ProjectManager, ProjectRecord
from bot_ia.core.router import Router
from bot_ia.core.session_store import PersistentSessionStore
from bot_ia.librarian import EntityIndex, SourceInventory
from bot_ia.librarian.models import CatalogEntry
from bot_ia.memory import MemoryStore
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
    memory_store: MemoryStore
    project_manager: ProjectManager | None = None
    workspace_root: Path = Path(".")
    _universe_map: dict[str, UniverseRuntime] = field(default_factory=dict, repr=False, compare=False)
    _runtime_lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_universe_map", {item.definition.universe_id: item for item in self.universes})

    def universe(self, universe_id: str) -> UniverseRuntime:
        with self._runtime_lock:
            try:
                return self._universe_map[universe_id]
            except KeyError as error:
                raise KeyError(f"universe not configured: {universe_id}") from error

    def configured_universe_ids(self) -> tuple[str, ...]:
        with self._runtime_lock:
            return tuple(self._universe_map)

    @property
    def backup_service(self) -> BackupService:
        """Return the local-only backup service for this runtime workspace."""
        return BackupService(self.workspace_root)

    def create_backup_snapshot(self, destination_root: Path, *, label: str) -> BackupSnapshot:
        """Create a validated snapshot of persistent memory and session state."""
        return self.backup_service.create_snapshot(destination_root, label=label)

    def build_tavern_manager(
        self,
        *,
        web_queue_manager: object | None = None,
        message_sender=None,
        message_deleter=None,
        timezone_name: str = "America/Argentina/Buenos_Aires",
    ) -> WaitressSessionManager:
        return WaitressSessionManager(
            self.memory_store.path,
            web_queue_manager=web_queue_manager,
            message_sender=message_sender,
            message_deleter=message_deleter,
            timezone_name=timezone_name,
        )

    def build_mama_mia_supervisor(
        self,
        *,
        gemini_responder=None,
        gemini_auditor=None,
    ) -> MamaMiaSupervisor:
        return MamaMiaSupervisor(
            self.memory_store.path,
            gemini_responder=gemini_responder,
            gemini_auditor=gemini_auditor,
        )

    def build_application(self, *, default_universe_id: str | None = None, provider_id: str = "openai") -> BotApplication:
        provider_config = self.registry.provider(provider_id)
        entries_by_universe = {universe.definition.universe_id: universe.entries for universe in self.universes}
        entity_indexes_by_universe = {universe.definition.universe_id: universe.entity_index for universe in self.universes}

        def candidate_provider(universe_id: str) -> tuple:
            return self.universe(universe_id).entity_index.for_universe(universe_id)

        workflow = LocalWorkflow(entries_by_universe, entity_indexes=entity_indexes_by_universe, provider_manager=self.provider_manager, memory_store=self.memory_store, provider_config=provider_config)
        session_store = PersistentSessionStore(self.workspace_root / "work" / "bot_ia_sessions.sqlite3")
        return BotApplication(LocalBrain(self.universe_registry), Router(), session_store, default_universe_id=default_universe_id, candidate_provider=candidate_provider, executor=workflow)

    def create_novel(self, display_name: str, *, application: BotApplication | None = None) -> ProjectRecord:
        with self._runtime_lock:
            if self.project_manager is None:
                raise RuntimeError("dynamic project manager is not configured")
            record = self.project_manager.create_novel(display_name)
            definition = UniverseDefinition(
                universe_id=record.project_id,
                display_name=record.display_name,
                root_path=record.root_path / "biblioteca",
                spoiler_policy="strict",
                language="es",
            )
            entries = SourceInventory(definition.root_path).discover(definition.universe_id)
            runtime = UniverseRuntime(definition, entries, EntityIndex(entries))
            self.universe_registry.register(definition)
            self._universe_map[definition.universe_id] = runtime
            object.__setattr__(self, "universes", (*self.universes, runtime))
            if application is not None:
                application.register_universe(definition, entries)
            return record


def _build_universe_runtime(config: RuntimeConfig) -> tuple[UniverseRegistry, tuple[UniverseRuntime, ...]]:
    registry = UniverseRegistry()
    universes: list[UniverseRuntime] = []
    for universe in config.universes:
        definition = UniverseDefinition(universe_id=universe.universe_id, display_name=universe.display_name, root_path=universe.root_path, spoiler_policy=universe.spoiler_policy, language=universe.language)
        registry.register(definition)
        entries = SourceInventory(definition.root_path).discover(definition.universe_id) if universe.root_path.is_dir() else ()
        universes.append(UniverseRuntime(definition, entries, EntityIndex(entries)))
    return registry, tuple(universes)


def build_runtime(project_root: Path, *, key_loader=None, transports=None) -> RuntimeComponents:
    project_root = project_root.resolve()
    config = load_default_runtime_config(project_root)
    registry = RuntimeRegistry(config)
    universe_registry, universes = _build_universe_runtime(config)
    project_manager = ProjectManager(project_root)
    for project in project_manager.all():
        definition = UniverseDefinition(universe_id=project.project_id, display_name=project.display_name, root_path=project.root_path / "biblioteca", spoiler_policy="strict", language="es")
        if universe_registry.contains(definition.universe_id):
            continue
        universe_registry.register(definition)
        entries = SourceInventory(definition.root_path).discover(definition.universe_id)
        universes = (*universes, UniverseRuntime(definition, entries, EntityIndex(entries)))
    provider_manager = build_provider_manager(config, key_loader=key_loader, transports=transports)
    memory_store = MemoryStore(project_root, universe_registry)
    return RuntimeComponents(config, registry, universe_registry, universes, provider_manager, memory_store, project_manager, project_root)
