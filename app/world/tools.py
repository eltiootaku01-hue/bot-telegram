from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WorldToolMode(StrEnum):
    READ = "read"
    EXECUTE = "execute"


@dataclass(frozen=True, slots=True)
class WorldToolPermission:
    """Explicit permission granted to the independent world runtime."""

    tool_id: str
    mode: WorldToolMode
    description: str
    enabled: bool = True
    requires_human_approval: bool = False

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("world tool id must not be empty")


DEFAULT_WORLD_TOOLS: tuple[WorldToolPermission, ...] = (
    WorldToolPermission(
        "world.catalog.read",
        WorldToolMode.READ,
        "Leer definiciones autorizadas del mundo.",
    ),
    WorldToolPermission(
        "world.state.read",
        WorldToolMode.READ,
        "Leer estados persistidos de eventos y juegos.",
    ),
    WorldToolPermission(
        "world.schedule",
        WorldToolMode.EXECUTE,
        "Programar eventos persistentes del mundo.",
    ),
    WorldToolPermission(
        "telegram.publish",
        WorldToolMode.EXECUTE,
        "Publicar una presentación de mundo en un chat autorizado.",
    ),
    WorldToolPermission(
        "external.web.read",
        WorldToolMode.READ,
        "Consultar una fuente web externa cuando el flujo lo autorice.",
        enabled=False,
    ),
    WorldToolPermission(
        "external.image.generate",
        WorldToolMode.EXECUTE,
        "Solicitar generación de arte externa para un evento.",
        enabled=False,
        requires_human_approval=True,
    ),
    WorldToolPermission(
        "world.ai.curate",
        WorldToolMode.EXECUTE,
        "Pedir a la IA una propuesta de expansión no canónica.",
        enabled=False,
        requires_human_approval=True,
    ),
)


class WorldToolPolicy:
    """Fail-closed allowlist for external/tool access.

    The policy is deliberately independent from the four character identities.
    A tool is available to the world runtime only when explicitly enabled.
    """

    def __init__(self, permissions: tuple[WorldToolPermission, ...] = DEFAULT_WORLD_TOOLS) -> None:
        self._permissions = {permission.tool_id: permission for permission in permissions}

    def get(self, tool_id: str) -> WorldToolPermission | None:
        return self._permissions.get(tool_id)

    def allowed(
        self,
        tool_id: str,
        *,
        human_approved: bool = False,
    ) -> bool:
        permission = self._permissions.get(tool_id)
        if permission is None or not permission.enabled:
            return False
        if permission.requires_human_approval and not human_approved:
            return False
        return True

    def all(self) -> tuple[WorldToolPermission, ...]:
        return tuple(self._permissions.values())
