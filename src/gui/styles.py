# -*- coding: utf-8 -*-
"""QSS modular para la interfaz Dark Cozy de Café Otaku."""

BASE_QSS = """
QMainWindow, QWidget {
    background: #0f1117;
    color: #f2f3f7;
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
}
QFrame#Sidebar {
    background: #12151d;
    border-right: 1px solid #262b36;
}
QFrame#TopBar, QFrame#FooterBar {
    background: #12151d;
    border: 1px solid #262b36;
    border-radius: 14px;
}
QFrame#Card {
    background: #161a23;
    border: 1px solid #2a303c;
    border-radius: 16px;
}
QLabel#BrandTitle {
    color: #f7d7e8;
    font-size: 20px;
    font-weight: 700;
}
QLabel#PageTitle {
    color: #f3f4f8;
    font-size: 18px;
    font-weight: 700;
}
QLabel#Muted {
    color: #9299a8;
}
QLabel#StatusDot[status="online"] { color: #9be7c3; }
QLabel#StatusDot[status="warn"] { color: #f2d38f; }
QLabel#StatusDot[status="offline"] { color: #ef9ba8; }
QPushButton {
    background: #202632;
    color: #eef0f5;
    border: 1px solid #303746;
    border-radius: 12px;
    padding: 9px 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: #262d3b;
    border-color: #40495a;
}
QPushButton:pressed {
    background: #1b202a;
}
QPushButton:disabled {
    background: #181c24;
    color: #616879;
    border-color: #232833;
}
QPushButton#AccentButton {
    background: #c88cad;
    color: #17131a;
    border: none;
}
QPushButton#AccentButton:hover { background: #d9a4bf; }
QPushButton#Chip {
    background: #191e28;
    border: 1px solid #353c4b;
    border-radius: 18px;
    padding: 8px 12px;
}
QPushButton#Chip:hover {
    background: #242b37;
    border-color: #6e7688;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background: #11151c;
    color: #f1f3f7;
    border: 1px solid #2c3340;
    border-radius: 12px;
    padding: 9px 11px;
    selection-background-color: #6f4b63;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border-color: #8d617d;
}
QScrollArea, QScrollBar {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    width: 8px;
    margin: 3px;
}
QScrollBar::handle:vertical {
    background: #363d4a;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabBar::tab {
    background: transparent;
    color: #9299a8;
    padding: 8px 12px;
    border-radius: 9px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #222834;
    color: #f7d7e8;
}
QProgressBar {
    background: #10141b;
    border: 1px solid #2a303a;
    border-radius: 7px;
    text-align: center;
    color: #dfe2e8;
    min-height: 12px;
}
QProgressBar::chunk {
    background: #8abfa7;
    border-radius: 6px;
}
QToolTip {
    background: #1b2029;
    color: #f2f3f7;
    border: 1px solid #343b49;
    padding: 7px;
}
QMessageBox {
    background: #161a23;
}
"""

SIDEBAR_QSS = """
QPushButton#BotTile {
    text-align: left;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    padding: 8px;
}
QPushButton#BotTile:hover {
    background: #1a1f29;
    border-color: #2f3542;
}
QPushButton#BotTile[selected="true"] {
    background: #24202a;
    border-color: #6b4f63;
}
QLabel#BotAvatar {
    font-size: 22px;
}
QLabel#BotName {
    font-size: 13px;
    font-weight: 700;
}
QLabel#BotStatus {
    color: #8f97a7;
    font-size: 11px;
}
"""

CHAT_QSS = """
QLabel#BubbleUser {
    background: #4f3a54;
    color: #fbf8fb;
    border: 1px solid #6e506f;
    border-radius: 16px;
    padding: 10px 12px;
}
QLabel#BubbleBot {
    background: #1a1f28;
    color: #f0f2f6;
    border: 1px solid #2e3541;
    border-radius: 16px;
    padding: 10px 12px;
}
QLabel#BubbleSystem {
    background: #171b24;
    color: #abb1bf;
    border: 1px dashed #343a48;
    border-radius: 12px;
    padding: 9px 11px;
}
"""

def application_qss() -> str:
    return BASE_QSS + SIDEBAR_QSS + CHAT_QSS
