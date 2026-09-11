from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class StartupFailure:
    identity: str
    message: str
    returncode: int | None = None


@dataclass(frozen=True, slots=True)
class StartupResult:
    started: tuple[str, ...]
    failure: StartupFailure | None = None


class StartupSequence:
    """Run managed bot launches sequentially and stop on the first failure."""

    def __init__(
        self,
        identities: Sequence[str],
        launch: Callable[[str], object],
        health: Callable[[str, object], bool],
        stop: Callable[[str, object], None],
    ) -> None:
        self.identities = tuple(identities)
        self.launch = launch
        self.health = health
        self.stop = stop

    def run(self) -> StartupResult:
        started: list[tuple[str, object]] = []
        for identity in self.identities:
            try:
                process = self.launch(identity)
                if not self.health(identity, process):
                    self.stop_started(started)
                    return StartupResult(
                        tuple(item[0] for item in started),
                        StartupFailure(identity, "El proceso no superó la comprobación de salud"),
                    )
                started.append((identity, process))
            except Exception as exc:
                self.stop_started(started)
                return StartupResult(
                    tuple(item[0] for item in started),
                    StartupFailure(identity, str(exc), getattr(exc, "returncode", None)),
                )
        return StartupResult(tuple(item[0] for item in started))

    def stop_started(self, started: Sequence[tuple[str, object]]) -> None:
        for identity, process in reversed(started):
            try:
                self.stop(identity, process)
            except Exception:
                continue
