# -*- coding: utf-8 -*-
"""2F-8T cause discrimination 12: isolated Qt application state diagnostics only."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import textwrap
import time


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "tests" / "test_services_web_queue.py"
TARGET = ROOT / "tests" / "test_webchat_runtime_controlled_8h.py"


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--headless --disable-gpu --disable-software-rasterizer"
    )
    return env


def _run_child(label: str, code: str, timeout: int = 180) -> tuple[int, list[tuple[float, str]]]:
    env = _base_env()
    print("\n=== 2F8T CASE: " + label + " ===", flush=True)
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    captured: list[tuple[float, str]] = []
    assert process.stdout is not None
    try:
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n")
            relative = time.monotonic() - started
            captured.append((relative, line))
            print(f"[+{relative:8.3f}s] {line}", flush=True)
    finally:
        return_code = process.wait(timeout=timeout)
    print(
        f"[PROCESS] label={label} exit_code={return_code}",
        flush=True,
    )
    return return_code, captured


def _environment_child() -> str:
    return """
        import os
        import platform
        import sys
        from PySide6 import __version__ as pyside6_version
        from PySide6.QtCore import qVersion

        print("ENV os=" + platform.platform(), flush=True)
        print("ENV python=" + platform.python_version(), flush=True)
        print("ENV pyside6=" + pyside6_version, flush=True)
        print("ENV qt=" + qVersion(), flush=True)
        print("ENV QT_QPA_PLATFORM=" + repr(os.environ.get("QT_QPA_PLATFORM")), flush=True)
        print(
            "ENV QTWEBENGINE_CHROMIUM_FLAGS="
            + repr(os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS")),
            flush=True,
        )
    """


def _snapshot_child(label: str) -> str:
    return f"""
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication, QWidget
        from PySide6.QtWebEngineWidgets import QWebEngineView

        _core = QCoreApplication.instance()
        _gui = QGuiApplication.instance()
        _app = QApplication.instance()
        _widgets = QApplication.allWidgets() if _app is not None else []
        _views = [widget for widget in _widgets if isinstance(widget, QWebEngineView)]

        print(
            "SNAPSHOT {label} "
            f"qcore={{type(_core).__name__ if _core is not None else 'None'}} "
            f"qgui={{type(_gui).__name__ if _gui is not None else 'None'}} "
            f"qapp={{type(_app).__name__ if _app is not None else 'None'}} "
            f"top_level_widgets={{sum(1 for w in _widgets if isinstance(w, QWidget) and w.isWindow())}} "
            f"qwebengine_views={{len(_views)}} "
            f"qwebengine_pages={{sum(1 for w in _views if w.page() is not None)}}",
            flush=True,
        )
    """


def _webengine_child(app_type: str) -> str:
    app_setup = {
        "NONE": "",
        "QCoreApplication": "app = QCoreApplication(sys.argv)",
        "QGuiApplication": "app = QGuiApplication(sys.argv)",
        "QApplication": "app = QApplication(sys.argv)",
    }[app_type]
    return f"""
        import sys
        from PySide6.QtCore import QCoreApplication, QEventLoop, QUrl, QTimer
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView

        {_environment_child()}
        print("APP_TYPE_BEFORE={app_type}", flush=True)

        _before = QCoreApplication.instance()
        print(
            "APP_INSTANCE_BEFORE="
            + (type(_before).__name__ if _before is not None else "None"),
            flush=True,
        )

        app = None
        if {app_type!r} == "NONE":
            app = QApplication(sys.argv)
            print(
                "APP_CREATED_FOR_WIDGET_BASELINE="
                + type(QCoreApplication.instance()).__name__,
                flush=True,
            )
        else:
            {app_setup}

        _after_app = QCoreApplication.instance()
        print(
            "APP_INSTANCE_AT_QWEBENGINE_BOUNDARY="
            + (type(_after_app).__name__ if _after_app is not None else "None"),
            flush=True,
        )
        print("PHASE=BEFORE_QWEBENGINE_VIEW", flush=True)

        view = QWebEngineView()
        print("PHASE=QWEBENGINE_VIEW_CREATED", flush=True)

        loop = QEventLoop()
        loaded: list[bool] = []
        timeout_fired = [False]
        timer = QTimer()
        timer.setSingleShot(True)

        def _on_load_finished(ok: bool) -> None:
            print("PHASE=LOAD_FINISHED callback=" + str(bool(ok)), flush=True)
            loaded.append(bool(ok))
            loop.quit()

        def _on_timeout() -> None:
            timeout_fired[0] = True
            print("PHASE=LOAD_TIMEOUT", flush=True)
            loop.quit()

        view.loadFinished.connect(_on_load_finished)
        timer.timeout.connect(_on_timeout)

        print("PHASE=SET_HTML", flush=True)
        view.setHtml(
            "<!doctype html><html><head><meta charset='utf-8'></head>"
            "<body><div id='ok'>controlled</div></body></html>",
            QUrl("http://application-probe.local/"),
        )

        print("PHASE=WAIT_LOAD", flush=True)
        timer.start(5000)
        loop.exec()
        timer.stop()

        print(
            "WEBENGINE_RESULT "
            f"qwebengine_created=True "
            f"loadFinished={{loaded[-1] if loaded else 'NO_CALLBACK'}} "
            f"loaded={{loaded[-1] if loaded else False}} "
            f"timeout={{timeout_fired[0]}}",
            flush=True,
        )

        print(
            "TEARDOWN_BEFORE "
            f"page_exists={{view.page() is not None}}",
            flush=True,
        )
        view.close()
        view.deleteLater()
        if QCoreApplication.instance() is not None:
            QCoreApplication.instance().processEvents()
            QCoreApplication.instance().processEvents()
        print("TEARDOWN_AFTER close_deleteLater_processEvents", flush=True)

        if app is not None:
            del app
        if QCoreApplication.instance() is not None:
            print(
                "APP_INSTANCE_AFTER_DELETE="
                + type(QCoreApplication.instance()).__name__,
                flush=True,
            )
        else:
            print("APP_INSTANCE_AFTER_DELETE=None", flush=True)

        raise SystemExit(0 if loaded and loaded[-1] else 10)
    """


def _destroy_then_qapplication_child() -> str:
    return f"""
        import gc
        import sys
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtCore import QEventLoop, QUrl, QTimer

        {_environment_child()}
        print("APP_TYPE_BEFORE=QCoreApplication_CREATE_THEN_DESTROY", flush=True)

        app = QCoreApplication(sys.argv)
        print(
            "APP_INSTANCE_AFTER_QCORE_CREATE="
            + type(QCoreApplication.instance()).__name__,
            flush=True,
        )
        app = None
        gc.collect()
        residual = QCoreApplication.instance()
        print(
            "APP_INSTANCE_AFTER_QCORE_DESTROY="
            + (type(residual).__name__ if residual is not None else "None"),
            flush=True,
        )

        if residual is not None:
            print("STATE_SINGLETON_CLEAN=False", flush=True)
            raise SystemExit(125)

        app = QApplication(sys.argv)
        print(
            "APP_INSTANCE_AT_QAPPLICATION_BOUNDARY="
            + type(QCoreApplication.instance()).__name__,
            flush=True,
        )
        print("PHASE=BEFORE_QWEBENGINE_VIEW", flush=True)
        view = QWebEngineView()
        print("PHASE=QWEBENGINE_VIEW_CREATED", flush=True)

        loop = QEventLoop()
        loaded: list[bool] = []
        timed_out = [False]
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: (timed_out.__setitem__(0, True), loop.quit()))
        view.loadFinished.connect(lambda ok: (loaded.append(bool(ok)), loop.quit()))
        view.setHtml(
            "<!doctype html><html><body><div id='ok'>controlled</div></body></html>",
            QUrl("http://application-probe.local/"),
        )
        timer.start(5000)
        loop.exec()
        timer.stop()
        print(
            "WEBENGINE_RESULT "
            f"qwebengine_created=True "
            f"loadFinished={{loaded[-1] if loaded else 'NO_CALLBACK'}} "
            f"loaded={{loaded[-1] if loaded else False}} "
            f"timeout={{timed_out[0]}}",
            flush=True,
        )
        view.close()
        view.deleteLater()
        app.processEvents()
        app.processEvents()
        print("TEARDOWN_AFTER close_deleteLater_processEvents", flush=True)
        del app
        gc.collect()
        print(
            "APP_INSTANCE_FINAL="
            + (
                type(QCoreApplication.instance()).__name__
                if QCoreApplication.instance() is not None
                else "None"
            ),
            flush=True,
        )
        raise SystemExit(0 if loaded and loaded[-1] else 10)
    """


def _services_target_child() -> str:
    return f"""
        import pytest

        class _TargetLifecycleProbe:
            def pytest_collection_modifyitems(self, session, config, items):
                patched = False
                for item in items:
                    item_path = str(getattr(item, "path", ""))
                    if not item_path.endswith("test_webchat_runtime_controlled_8h.py"):
                        continue
                    harness_cls = getattr(
                        item.module,
                        "ControlledWebChatHarness",
                        None,
                    )
                    if harness_cls is None or patched:
                        continue
                    original_init = harness_cls.__init__

                    def _wrapped_init(self, *args, **kwargs):
                        print(
                            "=== SERVICES_CONTEXT BEFORE ControlledWebChatHarness ===",
                            flush=True,
                        )
                        {_snapshot_child("SERVICES_CONTEXT_PRE_HARNESS")}
                        return original_init(self, *args, **kwargs)

                    harness_cls.__init__ = _wrapped_init
                    patched = True

        {_environment_child()}
        print("=== SERVICES_CONTEXT PYTEST START ===", flush=True)
        raise SystemExit(
            pytest.main(
                [
                    "-q",
                    "-s",
                    {str(SERVICES)!r},
                    {str(TARGET)!r},
                ],
                plugins=[_TargetLifecycleProbe()],
            )
        )
    """


class CauseDiscrimination12Tests:
    def _repeat_case(self, case_label: str, code: str) -> None:
        for run in range(1, 4):
            exit_code, lines = _run_child(
                f"{case_label} RUN {run}/3",
                code,
                timeout=180,
            )
            print(
                f"[MATRIX] case={case_label} run={run}/3 exit_code={exit_code}",
                flush=True,
            )
            if not lines:
                raise AssertionError(
                    f"{case_label} run {run}/3 produced no output"
                )

    def test_2f8t_cause_discrimination_matrix(self, capsys) -> None:
        with capsys.disabled():
            cases = {
                "A_NONE": _webengine_child("NONE"),
                "B_QCORE": _webengine_child("QCoreApplication"),
                "C_QGUI": _webengine_child("QGuiApplication"),
                "D_QAPPLICATION": _webengine_child("QApplication"),
                "E_QCORE_DESTROY_THEN_QAPPLICATION": _destroy_then_qapplication_child(),
            }
            for label, code in cases.items():
                self._repeat_case(label, code)

    def test_2f8t_services_context_comparison(self, capsys) -> None:
        with capsys.disabled():
            for run in range(1, 4):
                exit_code, lines = _run_child(
                    f"SERVICES_CORE_PLUS_TARGET RUN {run}/3",
                    _services_target_child(),
                    timeout=240,
                )
                print(
                    f"[SERVICES-MATRIX] run={run}/3 exit_code={exit_code}",
                    flush=True,
                )
                if not lines:
                    raise AssertionError(
                        f"services context run {run}/3 produced no output"
                    )


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main(["-q", "-s", __file__]))
