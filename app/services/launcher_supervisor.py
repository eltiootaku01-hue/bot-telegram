from __future__ import annotations

from dataclasses import dataclass
from threading import Lock, Thread
from typing import Callable, Sequence

from app.services.process_manager import ProcessManager
from app.services.startup_sequence import StartupResult


@dataclass(frozen=True, slots=True)
class StartupTaskResult:
    result: StartupResult | None = None
    error: BaseException | None = None


class LauncherSupervisor:
    """Run blocking process supervision away from the Tk event loop."""

    def __init__(self, manager: ProcessManager) -> None:
        self.manager = manager
        self._lock = Lock()
        self._task: StartupTaskResult | None = None
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start_all(self, identities: Sequence[str], callback: Callable[[StartupTaskResult], None]) -> bool:
        with self._lock:
            if self.running:
                return False
            self._task = None
            self._thread = Thread(
                target=self._run,
                args=(tuple(identities), callback),
                daemon=True,
                name="bot-startup-supervisor",
            )
            self._thread.start()
        return True

    def _run(self, identities: tuple[str, ...], callback: Callable[[StartupTaskResult], None]) -> None:
        try:
            result = StartupTaskResult(result=self.manager.start_sequential(identities))
        except BaseException as exc:  # surface unexpected startup errors to the UI
            result = StartupTaskResult(error=exc)
        with self._lock:
            self._task = result
        callback(result)

    def stop_all(self) -> None:
        self.manager.stop_all()
