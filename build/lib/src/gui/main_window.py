from __future__ import annotations

import os
import sys

from PySide6.QtCore import QMetaObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QSplitter, QWidget

from .api_client import CommandCenterApiClient
from .map_scene import CafeMapScene, CafeMapView
from .models import StateSnapshot
from .sidebar_view import SidebarView
from .topic_mapper import TopicMapper
from .workers import CommandWorker, start_threaded_poller


class MainWindow(QMainWindow):
    command_requested = Signal(str, str, object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Casa de Comando — Otaku Café")
        self.resize(1320, 820)
        self.mapper = TopicMapper(os.getenv("COMMAND_CENTER_TOPICS_PATH", "config/forum_topics.json"))
        chat_id = os.getenv("COMMAND_CENTER_CHAT_ID")
        if chat_id:
            try:
                self.mapper.load_dynamic(int(chat_id), os.getenv("COMMAND_CENTER_DB_PATH", "data/command_center_events.db"))
            except ValueError:
                pass
        self.client = CommandCenterApiClient()
        self.latest: StateSnapshot | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        self.map_scene = CafeMapScene(self.mapper)
        self.map_view = CafeMapView(self.map_scene)
        splitter.addWidget(self.map_view)
        splitter.setStretchFactor(0, 3)

        self.sidebar = SidebarView(self.mapper)
        splitter.addWidget(self.sidebar)
        splitter.setStretchFactor(1, 2)
        self.sidebar.command_requested.connect(self._command)
        self.sidebar.binding_changed.connect(self.reassign_thread)

        self.command_thread = QThread(self)
        self.command_worker = CommandWorker(self.client)
        self.command_worker.moveToThread(self.command_thread)
        self.command_requested.connect(self.command_worker.execute, Qt.ConnectionType.QueuedConnection)
        self.command_worker.result.connect(lambda action, result: self.sidebar.log(f"RESULT {action}: {result}"))
        self.command_worker.error.connect(self._api_error)
        self.command_thread.start()

        self.poll_thread, self.poller = start_threaded_poller(self.client, self)
        self.poller.snapshot_ready.connect(self._snapshot_ready, Qt.ConnectionType.QueuedConnection)
        self.poller.error.connect(self._api_error, Qt.ConnectionType.QueuedConnection)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(120)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start()

    def _command(self, action: str, identity: str, payload: dict) -> None:
        self.sidebar.log(f"COMMAND {identity}: {action}")
        self.command_requested.emit(action, identity, payload)

    @Slot(object)
    def _snapshot_ready(self, snapshot: StateSnapshot) -> None:
        previous = {item.identity: item for item in self.latest.bots} if self.latest else {}
        self.latest = snapshot
        self.map_scene.apply_snapshot(snapshot)
        self.sidebar.refresh(snapshot)
        for item in snapshot.bots:
            old = previous.get(item.identity)
            if old and old.state != item.state:
                self.sidebar.log(f"FSM {item.identity}: {old.state} → {item.state}")

    def reassign_thread(self, identity: str, thread_id: int) -> None:
        self.map_scene.reassign_thread(identity, thread_id)
        self.sidebar.log(f"MAPPING {identity}: message_thread_id={thread_id}")

    def _api_error(self, message: str) -> None:
        self.sidebar.log(f"API ERROR: {message}")
        self.statusBar().showMessage(message)

    def _pulse(self) -> None:
        for avatar in self.map_scene.avatars.values():
            active = avatar.snapshot.state.upper() in {"IN_POKER_GAME", "PROCESSING_ROLL", "PROCESSING_INVENTORY", "COOLDOWN", "SECURITY_LOCKOUT"}
            avatar.setOpacity(0.78 if active and avatar.opacity() > 0.9 else 1.0 if active else 1.0)

    def closeEvent(self, event) -> None:
        QMetaObject.invokeMethod(self.poller, "stop", Qt.ConnectionType.QueuedConnection)
        self.poll_thread.quit()
        self.poll_thread.wait(1500)
        self.command_thread.quit()
        self.command_thread.wait(1500)
        super().closeEvent(event)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
