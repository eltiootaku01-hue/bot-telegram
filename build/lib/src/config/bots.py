from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WorkerIdentity(StrEnum):
    """Non-conversational workers managed by Casa de Comando."""

    SCARLET = "scarlet"
    CHLOE = "chloe"


@dataclass(frozen=True, slots=True)
class WorkerProfile:
    identity: WorkerIdentity
    display_name: str
    role: str


WORKER_PROFILES: dict[WorkerIdentity, WorkerProfile] = {
    WorkerIdentity.SCARLET: WorkerProfile(
        WorkerIdentity.SCARLET,
        "Scarlet",
        "Worker mecánico de redes y webhooks",
    ),
    WorkerIdentity.CHLOE: WorkerProfile(
        WorkerIdentity.CHLOE,
        "Chloe",
        "Worker de juego de cartas y Bóveda",
    ),
}


def get_worker_profile(identity: WorkerIdentity) -> WorkerProfile:
    return WORKER_PROFILES[identity]
