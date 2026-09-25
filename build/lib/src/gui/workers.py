from __future__ import annotations

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from .api_client import CommandCenterApiClient, CommandCenterApiError
from .models import StateSnapshot


class StatePoller(QObject):
    snapshot_ready = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, client: CommandCenterApiClient, interval_ms: int = 250) -> None:
        super().__init__()
        self.client = client
        self.interval_ms = max(100, interval_ms)
        self._timer: QTimer | None = None

    @Slot()
    def start(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self.poll)
        self._timer.start()
        self.poll()

    @Slot()
    def poll(self) -> None:
        try:
            payload, elapsed = self.client.state()
            self.snapshot_ready.emit(StateSnapshot.from_payload(payload, elapsed))
        except CommandCenterApiError as exc:
            self.error.emit(str(exc))

    @Slot()
    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self.finished.emit()


class CommandWorker(QObject):
    result = Signal(str, object)
    error = Signal(str)

    def __init__(self, client: CommandCenterApiClient) -> None:
        super().__init__()
        self.client = client

    @Slot(str, str, object)
    def execute(self, action: str, identity: str, payload: object) -> None:
        try:
            body = payload if isinstance(payload, dict) else {}
            response, elapsed = self.client.command(action, identity, body)
            self.result.emit(action, {"response": response, "latency_ms": elapsed})
        except CommandCenterApiError as exc:
            self.error.emit(str(exc))


def start_threaded_poller(client: CommandCenterApiClient, parent: QObject | None = None) -> tuple[QThread, StatePoller]:
    thread = QThread(parent)
    worker = StatePoller(client)
    worker.moveToThread(thread)
    thread.started.connect(worker.start)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    return thread, worker
