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
    cancelled: bool = False


class StartupSequence:
    """Run managed bot launches sequentially and stop on the first failure."""

    def __init__(
        self,
        identities: Sequence[str],
        launch: Callable[[str], object],
        health: Callable[[str, object], bool],
        stop: Callable[[str, object], None],
        should_continue: Callable[[], bool] | None = None,
    ) -> None:
        self.identities = tuple(identities)
        self.launch = launch
        self.health = health
        self.stop = stop
        self.should_continue = should_continue or (lambda: True)

    def run(self) -> StartupResult:
        started: list[tuple[str, object]] = []
        for identity in self.identities:
            if not self.should_continue():
                self.stop_started(started)
                return StartupResult(tuple(), cancelled=True)
            try:
                process = self.launch(identity)
                if not self.should_continue():
                    self.stop_started((*started, (identity, process)))
                    return StartupResult(tuple(), cancelled=True)
                if not self.health(identity, process):
                    self.stop_started(started)
                    return StartupResult(
                        tuple(item[0] for item in started),
                        StartupFailure(
                            identity,
                            "El proceso no superó la comprobación de salud",
                            self._returncode(process),
                        ),
                    )
                if not self.should_continue():
                    self.stop_started((*started, (identity, process)))
                    return StartupResult(tuple(), cancelled=True)
                started.append((identity, process))
            except Exception as exc:
                self.stop_started(started)
                return StartupResult(
                    tuple(item[0] for item in started),
                    StartupFailure(identity, str(exc), getattr(exc, "returncode", None)),
                )
        return StartupResult(tuple(item[0] for item in started))

    @staticmethod
    def _returncode(process: object) -> int | None:
        poll = getattr(process, "poll", None)
        return poll() if callable(poll) else None

    def stop_started(self, started: Sequence[tuple[str, object]]) -> None:
        for identity, process in reversed(started):
            try:
                self.stop(identity, process)
            except Exception:
                continue
