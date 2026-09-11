from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Sequence

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
        self._results: Queue[StartupTaskResult] = Queue()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start_all(self, identities: Sequence[str]) -> bool:
        with self._lock:
            if self.running:
                return False
            self._thread = Thread(
                target=self._run,
                args=(tuple(identities),),
                daemon=True,
                name="bot-startup-supervisor",
            )
            self._thread.start()
        return True

    def _run(self, identities: tuple[str, ...]) -> None:
        try:
            result = StartupTaskResult(result=self.manager.start_sequential(identities))
        except BaseException as exc:  # surface unexpected startup errors to the UI
            result = StartupTaskResult(error=exc)
        self._results.put(result)

    def poll_result(self) -> StartupTaskResult | None:
        """Non-blocking result retrieval; safe to call from Tk's event loop."""
        try:
            result = self._results.get_nowait()
        except Empty:
            return None
        with self._lock:
            self._thread = None
        return result

    def stop_all(self) -> None:
        self.manager.stop_all()
