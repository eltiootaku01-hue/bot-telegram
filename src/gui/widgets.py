# -*- coding: utf-8 -*-
"""Widgets pequeños y reutilizables de Café Otaku."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CardFrame(QFrame):
    """Tarjeta con sombra discreta sin depender de estilos externos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(QPoint(0, 6))
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)


class BotTile(QPushButton):
    clicked_bot = Signal(str)

    def __init__(
        self,
        bot_id: str,
        avatar: str,
        name: str,
        status: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bot_id = bot_id
        self.setObjectName("BotTile")
        self.setCheckable(False)
        self.setMinimumHeight(64)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(9)

        avatar_label = QLabel(avatar)
        avatar_label.setObjectName("BotAvatar")
        avatar_label.setFixedSize(QSize(36, 36))
        avatar_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(avatar_label)

        body = QVBoxLayout()
        body.setSpacing(1)
        name_label = QLabel(name)
        name_label.setObjectName("BotName")
        status_label = QLabel(status)
        status_label.setObjectName("BotStatus")
        status_label.setWordWrap(True)
        body.addWidget(name_label)
        body.addWidget(status_label)
        layout.addLayout(body, 1)

        dot = QLabel("●")
        dot.setObjectName("StatusDot")
        dot.setProperty("status", "online")
        dot.setAlignment(Qt.AlignCenter)
        layout.addWidget(dot)
        self.status_label = status_label
        self.dot = dot

        self.clicked.connect(lambda: self.clicked_bot.emit(self.bot_id))

    def set_status(self, status: str, state: str) -> None:
        self.status_label.setText(status)
        self.dot.setProperty("status", state)
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class PillButton(QPushButton):
    """Chip de acción rápida."""

    def __init__(
        self,
        text: str,
        action_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.action_id = action_id
        self.setObjectName("Chip")
        self.setCursor(Qt.PointingHandCursor)


class SectionHeader(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("Muted")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)


class FlatToolButton(QToolButton):
    def __init__(
        self,
        icon: QIcon,
        tooltip: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setIcon(icon)
        self.setToolTip(tooltip)
        self.setAutoRaise(True)


class ResizeFilter(QWidget):
    """Marcador para evitar imports huérfanos en plugins GUI; no intercepta eventos."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        return super().eventFilter(watched, event)
