# -*- coding: utf-8 -*-
"""Read-only Qt lifetime probe for 2F-8T blocker isolation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_LOG = os.environ.get("QT_LIFETIME_LOG")
_LAST: str | None = None


def _write(record: dict[str, Any]) -> None:
    line = json.dumps(record, sort_keys=True, default=str)
    print(f"[QT-LIFETIME] {line}", flush=True)
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _snapshot() -> dict[str, Any]:
    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView

        app = QApplication.instance()
        gui = QGuiApplication.instance()
        if app is None:
            return {
                "qapplication": False,
                "qguiapplication": bool(gui),
                "top_level_widgets": [],
                "webengine_views": [],
            }

        widgets = list(app.topLevelWidgets())
        web_views = [
            {
                "class": type(widget).__name__,
                "url": (
                    widget.url().toString()
                    if isinstance(widget, QWebEngineView)
                    else ""
                ),
                "visible": (
                    bool(widget.isVisible())
                    if isinstance(widget, QWebEngineView)
                    else False
                ),
            }
            for widget in widgets
            if isinstance(widget, QWebEngineView)
        ]
        platform_name = "UNKNOWN"
        platform = getattr(gui, "platformName", None)
        if callable(platform):
            try:
                platform_name = str(platform())
            except Exception:
                platform_name = "PLATFORM_QUERY_ERROR"
        return {
            "qapplication": True,
            "qguiapplication": bool(gui),
            "application_name": str(app.applicationName()),
            "platform_name": platform_name,
            "top_level_widgets": sorted(type(widget).__name__ for widget in widgets),
            "webengine_views": web_views,
        }
    except Exception as exc:
        return {
            "probe_error": f"{type(exc).__name__}:{exc}",
        }


def _observe(phase: str, nodeid: str) -> None:
    global _LAST
    snapshot = _snapshot()
    encoded = json.dumps(snapshot, sort_keys=True, default=str)
    if encoded == _LAST:
        return
    _LAST = encoded
    _write(
        {
            "phase": phase,
            "nodeid": nodeid,
            "snapshot": snapshot,
        }
    )


def pytest_runtest_logstart(
    nodeid: str,
    location: tuple[str, int | None, str],
) -> None:
    _observe("logstart", nodeid)


def pytest_runtest_teardown(nodeid: str, nextitem: object | None) -> None:
    _observe("teardown", nodeid)


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    _observe("sessionfinish", "<session>")
    _write(
        {
            "phase": "sessionfinish",
            "exitstatus": exitstatus,
            "final_snapshot": _snapshot(),
            "cwd": str(Path.cwd()),
        }
    )
