# -*- coding: utf-8 -*-
"""2F-8T diagnostic isolation only. No production behavior is changed."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "test_webchat_runtime_controlled_8h.py"
SERVICES = ROOT / "tests" / "test_services_web_queue.py"


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--headless --disable-gpu --disable-software-rasterizer"
    )
    return env


def _run_child(label: str, code: str, timeout: int = 180) -> None:
    print("\n=== 2F8T DIAGNOSTIC: " + label + " ===", flush=True)
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT,
        env=_base_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    print("return_code=" + str(result.returncode), flush=True)
    combined = (result.stdout or "") + (result.stderr or "")
    lines = combined.splitlines()
    for line in lines[-80:]:
        print(line, flush=True)


def _instrumented_target_copy(temp_dir: Path) -> Path:
    source = TARGET.read_text(encoding="utf-8")
    marker = "        cls.harness = ControlledWebChatHarness()"
    probe = """
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication

        _qcore = QCoreApplication.instance()
        _qgui = QGuiApplication.instance()
        _qapp = QApplication.instance()
        print(
            "TARGET_PRE_HARNESS "
            f"qcore={type(_qcore).__name__ if _qcore is not None else 'None'} "
            f"qgui={type(_qgui).__name__ if _qgui is not None else 'None'} "
            f"qapp={type(_qapp).__name__ if _qapp is not None else 'None'}",
            flush=True,
        )
"""
    if marker not in source:
        raise AssertionError("target instrumentation marker not found")
    instrumented = source.replace(marker, textwrap.dedent(probe) + marker, 1)
    path = temp_dir / "test_webchat_runtime_controlled_8h_diag.py"
    path.write_text(instrumented, encoding="utf-8")
    return path


def _application_probe(app_type: str) -> str:
    return f"""
        import gc
        import sys

        from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWidgets import QApplication

        APP_TYPE = {app_type!r}
        app = None
        if APP_TYPE == "QCoreApplication":
            app = QCoreApplication(sys.argv)
        elif APP_TYPE == "QGuiApplication":
            app = QGuiApplication(sys.argv)
        elif APP_TYPE == "QApplication":
            app = QApplication(sys.argv)

        before = QCoreApplication.instance()
        print(
            "APP_BEFORE "
            f"requested={APP_TYPE} "
            f"actual={type(before).__name__ if before is not None else 'None'}",
            flush=True,
        )

        view = QWebEngineView()
        loaded = []
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
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
            f"loaded={{loaded[-1] if loaded else 'NO_CALLBACK'}}",
            flush=True,
        )
        view.close()
        view.deleteLater()
        if app is not None:
            app.processEvents()
        """


class RootCauseIsolationTests(unittest.TestCase):
    def test_2f8t_diagnostic_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            target_copy = _instrumented_target_copy(temp_dir)

            _run_child(
                "TARGET SOLO",
                f"""
                import pytest
                raise SystemExit(
                    pytest.main(["-q", {str(target_copy)!r}])
                )
                """,
            )

            for app_type in (
                "QCoreApplication",
                "QApplication",
                "QGuiApplication",
            ):
                _run_child(
                    "APP TYPE PROBE " + app_type,
                    _application_probe(app_type),
                )

            _run_child(
                "QCORE LIVE THEN TARGET",
                f"""
                import sys
                import pytest
                from PySide6.QtCore import QCoreApplication

                app = QCoreApplication(sys.argv)
                print(
                    "PRE_PYTEST_APP "
                    f"{{type(QCoreApplication.instance()).__name__}}",
                    flush=True,
                )
                raise SystemExit(
                    pytest.main(["-q", {str(target_copy)!r}])
                )
                """,
            )

            _run_child(
                "QAPPLICATION LIVE THEN TARGET",
                f"""
                import sys
                import pytest
                from PySide6.QtWidgets import QApplication

                app = QApplication(sys.argv)
                print(
                    "PRE_PYTEST_APP "
                    f"{{type(QApplication.instance()).__name__}}",
                    flush=True,
                )
                raise SystemExit(
                    pytest.main(["-q", {str(target_copy)!r}])
                )
                """,
            )

            _run_child(
                "QGUI LIVE THEN TARGET",
                f"""
                import sys
                import pytest
                from PySide6.QtGui import QGuiApplication

                app = QGuiApplication(sys.argv)
                print(
                    "PRE_PYTEST_APP "
                    f"{{type(QGuiApplication.instance()).__name__}}",
                    flush=True,
                )
                raise SystemExit(
                    pytest.main(["-q", {str(target_copy)!r}])
                )
                """,
            )

            _run_child(
                "QCORE CREATE DELETE THEN TARGET",
                f"""
                import gc
                import sys
                import pytest
                from PySide6.QtCore import QCoreApplication

                app = QCoreApplication(sys.argv)
                del app
                gc.collect()
                print(
                    "POST_DELETE_APP "
                    f"{{QCoreApplication.instance()}}",
                    flush=True,
                )
                raise SystemExit(
                    pytest.main(["-q", {str(target_copy)!r}])
                )
                """,
            )

            _run_child(
                "SERVICES ORIGINAL THEN TARGET",
                f"""
                import pytest
                raise SystemExit(
                    pytest.main(
                        [
                            "-q",
                            {str(SERVICES)!r},
                            {str(target_copy)!r},
                        ]
                    )
                )
                """,
                timeout=240,
            )

            services_text = SERVICES.read_text(encoding="utf-8")
            services_qapp = services_text.replace(
                "from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal, Slot",
                "from PySide6.QtCore import QObject, Qt, Signal, Slot",
            ).replace(
                "app = QCoreApplication.instance() or QCoreApplication([])",
                "from PySide6.QtWidgets import QApplication\n"
                "        app = QApplication.instance() or QApplication([])",
            )
            services_copy = temp_dir / "test_services_web_queue_qapp_diag.py"
            services_copy.write_text(services_qapp, encoding="utf-8")

            _run_child(
                "SERVICES QAPPLICATION VARIANT THEN TARGET",
                f"""
                import pytest
                raise SystemExit(
                    pytest.main(
                        [
                            "-q",
                            {str(services_copy)!r},
                            {str(target_copy)!r},
                        ]
                    )
                )
                """,
                timeout=240,
            )

            _run_child(
                "CROSS ROUTE X20 THEN TARGET",
                f"""
                import pytest
                raise SystemExit(
                    pytest.main(
                        [
                            "-q",
                            "tests/test_cross_route_physical_resource_exclusivity.py::"
                            "CrossRoutePhysicalExclusivityTests::"
                            "test_x20_controlled_cross_route_runtime_with_real_qweb_and_playwright",
                            {str(target_copy)!r},
                        ]
                    )
                )
                """,
                timeout=240,
            )

            _run_child(
                "PRODUCTION S03 THEN TARGET",
                f"""
                import pytest
                raise SystemExit(
                    pytest.main(
                        [
                            "-q",
                            "tests/test_production_runtime_lifecycle_8s.py::"
                            "ProductionRuntimeLifecycle8STests::"
                            "test_s03_qweb_controlled_lifecycle_binds_to_application_reconciliation",
                            {str(target_copy)!r},
                        ]
                    )
                )
                """,
                timeout=240,
            )

    def test_2f8t_static_application_inventory(self) -> None:
        print("\n=== 2F8T STATIC APPLICATION INVENTORY ===", flush=True)
        names = (
            "QCoreApplication(",
            "QApplication(",
            "QGuiApplication(",
            "QCoreApplication.instance()",
            "QApplication.instance()",
            "QGuiApplication.instance()",
            "QWebEngineView(",
            "@pytest.fixture",
            "autouse=True",
        )
        found: list[str] = []
        for path in sorted((ROOT / "tests").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            matches = [
                f"{path.relative_to(ROOT)}:{index}: {line.strip()}"
                for index, line in enumerate(lines, 1)
                if any(token in line for token in names)
            ]
            if matches:
                found.extend(matches)
        for line in found:
            print(line, flush=True)


if __name__ == "__main__":
    unittest.main()
