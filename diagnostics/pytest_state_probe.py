# -*- coding: utf-8 -*-
"""Read-only pytest/Qt state observer for phase 2F-8T-I."""

from __future__ import annotations

import os
from pathlib import Path
import sys


_TARGET = os.environ.get(
    "I_TARGET_NODEID",
    "tests/test_webchat_runtime_controlled_8h.py::WebChatRuntimeControlledTests",
)


def _emit(name: str, value: object) -> None:
    path = os.environ.get("I_STATE_LOG")
    line = f"{name}={value}"
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    print(f"[I-STATE] {line}", flush=True)


def _qt_state() -> None:
    try:
        from PySide6.QtCore import QCoreApplication, QThread
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication

        core = QCoreApplication.instance()
        gui = QGuiApplication.instance()
        app = QApplication.instance()

        _emit("QCOREAPPLICATION_EXISTS", bool(core))
        _emit("QGUIAPPLICATION_EXISTS", bool(gui))
        _emit("QAPPLICATION_EXISTS", bool(app))

        if app:
            _emit("QAPPLICATION_NAME", app.applicationName())
            _emit("QPA_BACKEND", app.platformName())
            try:
                _emit(
                    "TOP_LEVEL_WIDGETS",
                    [
                        type(widget).__name__
                        for widget in QApplication.topLevelWidgets()
                    ],
                )
            except Exception as exc:
                _emit("TOP_LEVEL_WIDGETS_ERROR", type(exc).__name__)
        else:
            _emit("QAPPLICATION_NAME", "NONE")
            _emit("QPA_BACKEND", "NONE")
            _emit("TOP_LEVEL_WIDGETS", "NONE")

        current = QThread.currentThread()
        _emit("QTHREAD_CURRENT", repr(current))
        _emit(
            "QTHREAD_OBJECT_NAME",
            current.objectName() if current else "NONE",
        )
        _emit(
            "QTHREAD_RUNNING",
            current.isRunning() if current else "NONE",
        )
        _emit(
            "QTHREAD_FINISHED",
            current.isFinished() if current else "NONE",
        )
        current_thread_id = getattr(QThread, "currentThreadId", None)
        if current_thread_id is not None:
            try:
                _emit("QTHREAD_CURRENT_ID", current_thread_id())
            except Exception as exc:
                _emit("QTHREAD_CURRENT_ID_ERROR", type(exc).__name__)
        else:
            _emit("QTHREAD_CURRENT_ID", "API_UNAVAILABLE")

        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

            views = []
            if app:
                views = [
                    type(widget).__name__
                    for widget in QApplication.topLevelWidgets()
                    if isinstance(widget, QWebEngineView)
                ]
            _emit("QWEBENGINE_TOP_LEVEL_VIEWS", views)
            _emit(
                "QWEBENGINE_APIS",
                {
                    "QWebEngineView": QWebEngineView.__module__,
                    "QWebEnginePage": QWebEnginePage.__module__,
                    "QWebEngineProfile": QWebEngineProfile.__module__,
                },
            )
        except Exception as exc:
            _emit("QWEBENGINE_OBSERVATION_ERROR", type(exc).__name__)

    except Exception as exc:
        _emit("QT_OBSERVATION_ERROR", f"{type(exc).__name__}:{exc}")


def _environment() -> None:
    for key in (
        "QT_QPA_PLATFORM",
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XDG_SESSION_TYPE",
        "TMPDIR",
        "TEMP",
        "TMP",
    ):
        _emit(f"ENV_{key}", os.environ.get(key, ""))

    _emit("CWD", str(Path.cwd()))
    relevant = sorted(
        name
        for name in sys.modules
        if name == "pytest"
        or name.startswith("pytest_")
        or name.startswith("PySide6")
    )
    _emit("RELEVANT_SYS_MODULES", relevant)


def pytest_runtest_logstart(nodeid: str, location: tuple[str, int | None, str]) -> None:
    if nodeid == _TARGET or nodeid.startswith(_TARGET + "::"):
        _emit("TARGET_NODEID", nodeid)
        _environment()
        _qt_state()
