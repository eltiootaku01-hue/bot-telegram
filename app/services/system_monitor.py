from __future__ import annotations

from dataclasses import dataclass

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is declared by the project
    psutil = None


@dataclass(frozen=True, slots=True)
class SystemSnapshot:
    cpu_percent: float
    memory_percent: float
    disk_percent: float


def snapshot(path: str = ".") -> SystemSnapshot:
    """Return a cheap local resource snapshot for the Manager UI."""
    if psutil is None:
        return SystemSnapshot(0.0, 0.0, 0.0)
    return SystemSnapshot(
        cpu_percent=float(psutil.cpu_percent(interval=None)),
        memory_percent=float(psutil.virtual_memory().percent),
        disk_percent=float(psutil.disk_usage(path).percent),
    )
