from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QGroupBox, QLabel, QListWidget, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .models import BOT_IDENTITIES, StateSnapshot
from .topic_mapper import TopicMapper


class SidebarView(QWidget):
    command_requested = Signal(str, str, object)
    binding_changed = Signal(str, int)

    def __init__(self, mapper: TopicMapper) -> None:
        super().__init__()
        self.mapper = mapper
        layout = QVBoxLayout(self)
        self._build_controls(layout)
        self._build_topics(layout)
        self._build_feed(layout)

    def _build_controls(self, parent):
        box = QGroupBox("Bot Control Grid")
        grid = QGridLayout(box)
        for row, identity in enumerate(BOT_IDENTITIES):
            grid.addWidget(QLabel(identity.title()), row, 0)
            for col, action, label in ((1, "cooldown", "Force Cooldown"), (2, "inventory", "Inspect Inventory"), (3, "security_lockout", "Security Lockout")):
                button = QPushButton(label)
                button.clicked.connect(lambda _, a=action, i=identity: self.command_requested.emit(a, i, {}))
                grid.addWidget(button, row, col)
        parent.addWidget(box)

    def _build_topics(self, parent):
        box = QGroupBox("Forum Topics Mapping")
        layout = QVBoxLayout(box)
        self.topic_table = QTableWidget(0, 5)
        self.topic_table.setHorizontalHeaderLabels(["Bot Identity", "Forum Topic (Thread ID)", "Table/Zone", "Current State", "Latency (local/net)"])
        self.topic_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.topic_table)
        parent.addWidget(box)

    def _build_feed(self, parent):
        box = QGroupBox("Live Activity Feed")
        layout = QVBoxLayout(box)
        self.feed = QListWidget()
        self.feed.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.feed)
        parent.addWidget(box, 1)

    def refresh(self, snapshot: StateSnapshot) -> None:
        self.topic_table.setRowCount(0)
        bindings = list(self.mapper.bindings())
        for row, item in enumerate(snapshot.bots):
            self.topic_table.insertRow(row)
            self.topic_table.setItem(row, 0, QTableWidgetItem(item.label))
            combo = QComboBox()
            combo.addItem("Unassigned", None)
            for binding in bindings:
                combo.addItem(f"{binding.zone} / {binding.thread_id}", binding)
            current = self.mapper.for_bot(item.identity)
            if current:
                idx = next((i for i in range(combo.count()) if combo.itemData(i) and combo.itemData(i).thread_id == current.thread_id), 0)
                combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(lambda _, i=item.identity, c=combo: self._select_binding(i, c))
            self.topic_table.setCellWidget(row, 1, combo)
            self.topic_table.setItem(row, 2, QTableWidgetItem(current.zone if current else item.zone))
            self.topic_table.setItem(row, 3, QTableWidgetItem(item.state))
            local = "—" if item.local_latency_ms is None else f"{item.local_latency_ms:.1f}"
            net = "—" if item.network_latency_ms is None else f"{item.network_latency_ms:.1f}"
            self.topic_table.setItem(row, 4, QTableWidgetItem(f"{local} / {net} ms"))

    def _select_binding(self, identity: str, combo: QComboBox) -> None:
        binding = combo.currentData()
        if binding is not None:
            self.binding_changed.emit(identity, binding.thread_id)

    def log(self, message: str) -> None:
        self.feed.addItem(message)
        self.feed.scrollToBottom()
