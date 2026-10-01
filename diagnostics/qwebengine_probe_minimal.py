# -*- coding: utf-8 -*-
"""Minimal, non-invasive QWebEngine diagnostic probe for phase 2F-8T-E."""

import os
import platform
import sys
import time

from PySide6.QtCore import QLibraryInfo, QTimer, QUrl, qVersion
from PySide6.QtWebEngineCore import QWebEngineProfile, qWebEngineChromiumVersion
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication


HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>QWebEngine Probe</title>
</head>
<body>
QWebEngine probe OK
</body>
</html>
"""

_ENV_KEYS = (
    "QT_QPA_PLATFORM",
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "QTWEBENGINEPROCESS_PATH",
    "QT_LOGGING_RULES",
    "QT_DEBUG_PLUGINS",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XDG_SESSION_TYPE",
)


def emit(name: str, value: object) -> None:
    print(f"{name}={value}", flush=True)


def rss_kib() -> str:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return line.split(":", 1)[1].strip()
    except (OSError, UnicodeError):
        pass
    return "UNAVAILABLE"


def main() -> int:
    started = time.monotonic()

    emit("EXIT_CODE", "PENDING")
    emit("OS", platform.platform())
    emit("KERNEL", platform.release())
    emit("ARCHITECTURE", platform.machine())
    emit("PYTHON", platform.python_version())
    emit("PYTHON_EXECUTABLE", sys.executable)
    emit("ARGV", repr(sys.argv))
    emit("PYSIDE6", __import__("PySide6").__version__)
    emit("QT", qVersion())
    emit("QT_PREFIX", QLibraryInfo.path(QLibraryInfo.LibraryPath.PrefixPath))
    emit(
        "QT_LIBEXEC",
        QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath),
    )
    emit("QWEBENGINE_CHROMIUM", qWebEngineChromiumVersion())
    emit("RSS_BEFORE_KIB", rss_kib())

    for key in _ENV_KEYS:
        emit(key, os.environ.get(key, ""))

    app = QApplication.instance() or QApplication(sys.argv)
    emit("QAPPLICATION_ARGS", repr(app.arguments()))
    emit("QPA_BACKEND", app.platformName())

    profile = QWebEngineProfile.defaultProfile()
    emit("PROFILE_OFF_THE_RECORD", profile.isOffTheRecord())
    emit("PROFILE_NAME", profile.storageName())
    emit("PROFILE_STORAGE_PATH", profile.persistentStoragePath())
    emit("PROFILE_CACHE_PATH", profile.cachePath())

    view = QWebEngineView()
    page = view.page()

    state = {
        "load_started": False,
        "load_finished_seen": False,
        "load_finished_ok": False,
    }

    def on_load_started() -> None:
        state["load_started"] = True
        emit("LOAD_STARTED", "True")
        emit("URL_AT_LOAD_STARTED", view.url().toString())

    def on_load_finished(ok: bool) -> None:
        state["load_finished_seen"] = True
        state["load_finished_ok"] = ok
        emit("LOAD_FINISHED", str(ok))
        emit("CURRENT_URL", view.url().toString())
        emit("PAGE_TITLE", view.title())
        emit("ELAPSED_MS", int((time.monotonic() - started) * 1000))
        emit("RSS_AFTER_LOAD_KIB", rss_kib())
        emit("PAGE_PROFILE_OFF_THE_RECORD", page.profile().isOffTheRecord())
        app.quit()

    view.loadStarted.connect(on_load_started)
    view.loadFinished.connect(on_load_finished)

    emit("SET_HTML_URL", "http://qwebengine-probe.local/")
    emit("PROBE_ACTION", "QWebEngineView.setHtml(minimal HTML)")
    view.setHtml(HTML, QUrl("http://qwebengine-probe.local/"))

    timer = QTimer()
    timer.setSingleShot(True)

    def on_timeout() -> None:
        emit("LOAD_FINISHED", "TIMEOUT")
        emit("LOAD_STARTED_SEEN", state["load_started"])
        emit("CURRENT_URL", view.url().toString())
        emit("PAGE_TITLE", view.title())
        emit("ELAPSED_MS", int((time.monotonic() - started) * 1000))
        emit("RSS_TIMEOUT_KIB", rss_kib())
        app.quit()

    timer.timeout.connect(on_timeout)
    timer.start(15000)

    app.exec()
    timer.stop()

    if not state["load_finished_seen"]:
        emit("EXIT_CODE", "2")
        return 2

    code = 0 if state["load_finished_ok"] else 1
    emit("EXIT_CODE", str(code))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
