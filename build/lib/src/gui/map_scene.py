from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsScene, QGraphicsView

from .models import BOT_IDENTITIES, BotSnapshot, StateSnapshot
from .topic_mapper import TopicMapper

STATE_ACTIVE = {"IN_POKER_GAME", "PROCESSING_ROLL", "PROCESSING_INVENTORY"}
STATE_WARNING = {"COOLDOWN", "SECURITY_LOCKOUT"}


def state_color(state: str) -> QColor:
    if state.upper() in STATE_ACTIVE:
        return QColor("#3bd16f")
    if state.upper() in STATE_WARNING:
        return QColor("#ffb020")
    return QColor("#a8b0bd")


class BotAvatar(QGraphicsObject):
    moved = Signal(str, float, float)

    def __init__(self, snapshot: BotSnapshot) -> None:
        super().__init__()
        self.identity = snapshot.identity
        self._snapshot = snapshot
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setToolTip(self.tooltip_text(snapshot))
        self.setPos(snapshot.x, snapshot.y)

    @property
    def snapshot(self) -> BotSnapshot:
        return self._snapshot

    @property
    def badge_color(self) -> QColor:
        return state_color(self._snapshot.state)

    def tooltip_text(self, snapshot: BotSnapshot | None = None) -> str:
        item = snapshot or self._snapshot
        thread = "—" if item.thread_id is None else str(item.thread_id)
        return f"{item.label}\nEstado: {item.state}\nmessage_thread_id: {thread}"

    def update_snapshot(self, snapshot: BotSnapshot, move_avatar: bool = True) -> None:
        self._snapshot = snapshot
        self.setToolTip(self.tooltip_text())
        if move_avatar:
            self.setPos(snapshot.x, snapshot.y)
        self.update()

    def set_topic_binding(self, thread_id: int | None, x: float, y: float) -> None:
        self.update_snapshot(
            BotSnapshot(
                identity=self._snapshot.identity,
                state=self._snapshot.state,
                thread_id=thread_id,
                zone=self._snapshot.zone,
                x=x,
                y=y,
                local_latency_ms=self._snapshot.local_latency_ms,
                network_latency_ms=self._snapshot.network_latency_ms,
                status=self._snapshot.status,
                metrics=self._snapshot.metrics,
            )
        )

    def boundingRect(self) -> QRectF:
        return QRectF(-34, -34, 68, 68)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        color = self.badge_color
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 3))
        painter.setBrush(QBrush(QColor(28, 32, 42, 235)))
        painter.drawEllipse(-25, -25, 50, 50)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(-8, -8, 16, 16)
        painter.setPen(QPen(QColor("#f1f3f5")))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(-30, 42, 60, 16, Qt.AlignmentFlag.AlignCenter, self.identity.title())
        if self._snapshot.state.upper() in STATE_WARNING:
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(17, -31, 12, 12)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            point = value
            self.moved.emit(self.identity, float(point.x()), float(point.y()))
        return super().itemChange(change, value)


class CafeMapScene(QGraphicsScene):
    def __init__(self, mapper: TopicMapper) -> None:
        super().__init__(0, 0, 760, 620)
        self.mapper = mapper
        self.avatars: dict[str, BotAvatar] = {}
        self.setBackgroundBrush(QColor("#11151d"))
        self._draw_floor_plan()

    def _draw_floor_plan(self) -> None:
        zones = [
            (60, 55, 260, 190, "POKER TABLE", "#203c2d"),
            (420, 55, 250, 150, "GACHA COUNTER", "#24344c"),
            (60, 330, 280, 190, "CATALOG DESK", "#3b3020"),
            (410, 330, 260, 190, "SECURITY DESK", "#3d2428"),
        ]
        for x, y, w, h, label, fill in zones:
            item = self.addRect(x, y, w, h, QPen(QColor("#566070"), 2), QBrush(QColor(fill)))
            item.setZValue(-10)
            text = self.addText(label, QFont("Segoe UI", 12, QFont.Weight.Bold))
            text.setDefaultTextColor(QColor("#e5e7eb"))
            text.setPos(x + 14, y + 12)
            text.setZValue(-9)
        title = self.addText("OTAKU CAFÉ — COMMAND CENTER", QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setDefaultTextColor(QColor("#f8fafc"))
        title.setPos(18, 10)
        title.setZValue(-8)

    def apply_snapshot(self, snapshot: StateSnapshot) -> None:
        by_id = {item.identity: item for item in snapshot.bots}
        for identity in BOT_IDENTITIES:
            data = by_id.get(identity)
            if data is None:
                binding = self.mapper.for_bot(identity)
                data = BotSnapshot(identity=identity, thread_id=binding.thread_id if binding else None,
                                   x=binding.x if binding else 100, y=binding.y if binding else 100,
                                   zone=binding.zone if binding else "cafe")
            avatar = self.avatars.get(identity)
            if avatar is None:
                avatar = BotAvatar(data)
                avatar.moved.connect(self._on_avatar_moved)
                self.addItem(avatar)
                self.avatars[identity] = avatar
            else:
                avatar.update_snapshot(data)

    def _on_avatar_moved(self, identity: str, x: float, y: float) -> None:
        binding = self.mapper.for_bot(identity)
        if binding is not None:
            binding.x, binding.y = x, y
            self.mapper.save()

    def reassign_thread(self, identity: str, thread_id: int) -> None:
        binding = self.mapper.for_bot(identity)
        if binding is None:
            raise ValueError(f"no mapping exists for {identity}")
        updated = self.mapper.reassign_thread(identity, thread_id)
        avatar = self.avatars.get(identity)
        if avatar is not None:
            avatar.set_topic_binding(updated.thread_id, updated.x, updated.y)
        self.mapper.save()


class CafeMapView(QGraphicsView):
    avatar_moved = Signal(str, float, float)

    def __init__(self, scene: CafeMapScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        for avatar in scene.avatars.values():
            avatar.moved.connect(self.avatar_moved)
