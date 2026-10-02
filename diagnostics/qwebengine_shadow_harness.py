# -*- coding: utf-8 -*-
"""Incremental shadow harness for phase 2F-8T-H.

This diagnostic reproduces only the pre-failure initialization delta of the
real controlled WebChat harness, one observable component per stage.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time


MINIMAL_HTML = """<!doctype html>
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

HARNESS_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Controlled WebChat</title></head>
<body>
  <main id="chat">
    <textarea id="prompt" aria-label="prompt"></textarea>
    <button id="send" aria-label="Enviar mensaje"
            onclick="window.__sendCount = (window.__sendCount || 0) + 1">
      Enviar
    </button>
    <section id="assistant" data-message-author-role="assistant"></section>
  </main>
</body>
</html>"""

PROBE_URL = "http://qwebengine-probe.local/"
HARNESS_URL = "http://controlled.local/"
TIMEOUT_MS = 5000


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


def add_src_to_path() -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def exact_wait_until(predicate) -> bool:
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)

    def check() -> None:
        if predicate():
            loop.quit()
            return
        QTimer.singleShot(20, check)

    QTimer.singleShot(0, check)
    timer.start(TIMEOUT_MS)
    loop.exec()
    timer.stop()
    return bool(predicate())


class CapturedBridge:
    """Diagnostic-only QObject bridge matching the real harness shape."""

    def __init__(self, QObject, Signal, Slot):
        class _Bridge(QObject):
            event_received = Signal(str, str)

            @Slot(str, str)
            def report(self, event_type: str, payload: str) -> None:
                self.event_received.emit(event_type, payload)

        self.type = _Bridge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stage = args.stage
    if stage < 0 or stage > 15:
        raise SystemExit("stage must be between 0 and 15")

    started = time.monotonic()
    emit("STAGE", stage)
    emit("RSS_BEFORE_KIB", rss_kib())

    # The real harness imports these Qt modules before setUpClass applies the
    # QPA/Chromium environment. Keeping the top-level imports here preserves
    # that ordering for the dedicated stage-11 environment-timing test.
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication

    QWebChannel = None
    QObject = None
    Signal = None
    Slot = None

    if stage >= 1:
        from PySide6.QtWebChannel import QWebChannel

    if stage >= 3:
        from PySide6.QtCore import QObject, Signal, Slot

    QEventLoop = None
    if stage >= 12:
        from PySide6.QtCore import QEventLoop

        emit("QEVENTLOOP_IMPORT", "True")

    if stage >= 9:
        add_src_to_path()
        import services.web_queue as _web_queue  # noqa: F401

        emit("PRODUCTION_IMPORT", "services.web_queue")

    if stage == 11:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS",
            "--headless --disable-gpu --disable-software-rasterizer",
        )
        emit("ENV_APPLIED_INSIDE_PROCESS", "True")

    if stage == 1:
        # Import-only delta: QWebChannel is available exactly as in the
        # harness, but no channel object is created yet.
        emit("QWEBCHANNEL_IMPORT", "True")

    bridge_type = None
    if stage >= 3:
        bridge_type = CapturedBridge(QObject, Signal, Slot).type

    if stage >= 13:
        QApplication(sys.argv)
        emit("PREEXISTING_QAPPLICATION", "created")

    app = QApplication.instance() or QApplication(sys.argv)
    emit("QAPPLICATION", "created")
    emit("QPA_BACKEND", app.platformName())
    emit("RSS_AFTER_QAPPLICATION_KIB", rss_kib())

    if stage >= 14:
        previous_view = QWebEngineView()
        previous_loop = QEventLoop()
        previous_timer = QTimer()
        previous_state = {"seen": False, "ok": False}

        def previous_loaded(ok: bool) -> None:
            previous_state["seen"] = True
            previous_state["ok"] = ok
            previous_loop.quit()

        previous_view.loadFinished.connect(previous_loaded)

        if stage >= 15:
            previous_channel = QWebChannel(previous_view.page())
            previous_bridge = bridge_type()
            previous_channel.registerObject(
                "casaQueueBridge",
                previous_bridge,
            )
            previous_view.page().setWebChannel(previous_channel)
            emit("PREVIOUS_WEBCHANNEL", "configured")

        previous_view.setHtml(
            MINIMAL_HTML,
            QUrl("http://qwebengine-prior.local/"),
        )
        previous_timer.setSingleShot(True)
        previous_timer.timeout.connect(previous_loop.quit)
        previous_timer.start(TIMEOUT_MS)
        previous_loop.exec()
        previous_timer.stop()
        emit(
            "PREVIOUS_WEBENGINE_LOAD_FINISHED",
            previous_state["ok"],
        )
        if not previous_state["seen"] or not previous_state["ok"]:
            emit("RESULT", "PRECONDITION_FAIL")
            emit("EXIT_CODE", 3)
            return 3
        previous_view.close()
        previous_view.deleteLater()
        app.processEvents()

    view = QWebEngineView()
    page = view.page()
    emit("QWEBENGINE_VIEW", "created")
    emit("RSS_AFTER_VIEW_KIB", rss_kib())

    channel = None
    bridge = None
    captured = []

    if stage >= 2:
        channel = QWebChannel(view.page())
        emit("QWEBCHANNEL_OBJECT", "created")

    if stage >= 3:
        bridge = bridge_type()
        emit("BRIDGE_OBJECT", "created")

    if stage >= 4:
        channel.registerObject("casaQueueBridge", bridge)
        emit("BRIDGE_REGISTERED", "True")

    if stage >= 5:
        view.page().setWebChannel(channel)
        emit("WEBCHANNEL_BOUND", "True")

    if stage >= 6:
        def capture(event_type: str, payload: str) -> None:
            captured.append((event_type, payload))

        bridge.event_received.connect(capture)
        emit("BRIDGE_SIGNAL_CONNECTED", "True")

    state = {
        "loaded": False,
        "load_finished_seen": False,
        "load_finished_ok": False,
    }

    def on_load_started() -> None:
        emit("LOAD_STARTED", "True")
        emit("URL_AT_LOAD_STARTED", view.url().toString())

    def on_loaded(ok: bool) -> None:
        state["load_finished_seen"] = True
        state["load_finished_ok"] = ok
        state["loaded"] = ok
        emit("LOAD_FINISHED_SIGNAL", str(ok))
        emit("CURRENT_URL", view.url().toString())
        emit("PAGE_TITLE", view.title())
        emit(
            "RSS_AFTER_LOAD_KIB",
            rss_kib(),
        )
        emit(
            "PAGE_PROFILE_OFF_THE_RECORD",
            page.profile().isOffTheRecord(),
        )

    view.loadStarted.connect(on_load_started)
    view.loadFinished.connect(on_loaded)

    html = HARNESS_HTML if stage >= 7 else MINIMAL_HTML
    url = HARNESS_URL if stage >= 8 else PROBE_URL

    emit("HTML_VARIANT", "HARNESS" if stage >= 7 else "MINIMAL")
    emit("SET_HTML_URL", url)
    emit("PROBE_ACTION", "QWebEngineView.setHtml")
    view.setHtml(html, QUrl(url))
    emit("RSS_AFTER_SET_HTML_KIB", rss_kib())

    if stage >= 10:
        waited = exact_wait_until(lambda: state["loaded"])
        emit("WAIT_MECHANISM", "HARNESS_WAIT_UNTIL")
        emit("WAIT_RETURNED", waited)
        if not state["load_finished_seen"]:
            emit("RESULT", "TIMEOUT")
            emit("EXIT_CODE", 2)
            return 2
    else:
        def quit_app() -> None:
            app.quit()

        view.loadFinished.connect(quit_app)
        app.exec()
        emit("WAIT_MECHANISM", "QAPPLICATION_EXEC")

    elapsed = int((time.monotonic() - started) * 1000)
    emit("ELAPSED_MS", elapsed)
    emit("LOAD_FINISHED", state["load_finished_ok"])
    emit("EVENT_COUNT", len(captured))
    emit("PROFILE_OFF_THE_RECORD", page.profile().isOffTheRecord())

    if not state["load_finished_seen"]:
        emit("RESULT", "TIMEOUT")
        emit("EXIT_CODE", 2)
        return 2

    if not state["load_finished_ok"]:
        emit("RESULT", "FAIL")
        emit("EXIT_CODE", 1)
        return 1

    emit("RESULT", "PASS")
    emit("EXIT_CODE", 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
