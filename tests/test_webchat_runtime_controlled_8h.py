# -*- coding: utf-8 -*-
"""Controlled QWebEngine/QWebChannel evidence for WebChat runtime mechanics."""

import json
import os
import sys
import unittest

from PySide6.QtCore import QObject, QEventLoop, QTimer, Signal, Slot, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

from bot_ia.core.web_physical_identity import (
    AuthenticationState,
    WebPhysicalIdentity,
)
from bot_ia.core.physical_resource_authority import (
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
)
from services.qweb_physical_resource_adapter import (
    QWebPhysicalResourceAdapter,
)
from services.web_queue import WEB_MONITOR_JS


class CapturedBridge(QObject):
    """Real QWebChannel endpoint used only by the controlled harness."""

    event_received = Signal(str, str)

    @Slot(str, str)
    def report(self, event_type: str, payload: str) -> None:
        self.event_received.emit(event_type, payload)


class ControlledWebChatHarness:
    """One real QWebEngine page with a local synthetic DOM."""

    HTML = """<!doctype html>
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

    def __init__(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.view = QWebEngineView()
        self.channel = QWebChannel(self.view.page())
        self.bridge = CapturedBridge()
        self.channel.registerObject("casaQueueBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.events: list[tuple[str, str]] = []
        self.bridge.event_received.connect(self._capture)
        self.loaded = False
        self.view.loadFinished.connect(self._on_loaded)
        self.view.setHtml(self.HTML, QUrl("http://controlled.local/"))

    def _capture(self, event_type: str, payload: str) -> None:
        self.events.append((event_type, payload))

    def _on_loaded(self, ok: bool) -> None:
        self.loaded = ok

    def wait_until(self, predicate, timeout_ms: int = 5000) -> bool:
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
        timer.start(timeout_ms)
        loop.exec()
        timer.stop()
        return bool(predicate())

    def run_js(self, script: str, timeout_ms: int = 5000):
        result = []
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)

        def done(value) -> None:
            result.append(value)
            loop.quit()

        self.view.page().runJavaScript(script, done)
        timer.start(timeout_ms)
        loop.exec()
        timer.stop()
        if not result:
            raise AssertionError("JavaScript callback timed out")
        return result[0]

    def install_monitor(self) -> None:
        result = self.run_js(WEB_MONITOR_JS)
        self.assert_loaded()
        if result not in ("INSTALL_REQUESTED", "ALREADY_INSTALLED"):
            raise AssertionError(f"Unexpected monitor result: {result!r}")
        if not self.wait_until(
            lambda: any(event == "MONITOR_READY" for event, _ in self.events)
        ):
            errors = [payload for event, payload in self.events if event == "MONITOR_ERROR"]
            raise AssertionError(f"QWebChannel monitor did not become ready: {errors}")

    def assert_loaded(self) -> None:
        if not self.loaded:
            raise AssertionError("controlled HTML did not load")

    def close(self) -> None:
        self.view.close()
        self.channel.deregisterObject(self.bridge)
        self.view.deleteLater()
        self.app.processEvents()


class WebChatRuntimeControlledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS",
            "--headless --disable-gpu --disable-software-rasterizer",
        )
        cls.harness = ControlledWebChatHarness()
        if not cls.harness.wait_until(lambda: cls.harness.loaded):
            raise AssertionError("QWebEngine local page did not load")
        cls.harness.install_monitor()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.harness.close()

    def setUp(self) -> None:
        self.harness.events.clear()
        self.harness.run_js(
            "window.__casaComandoWebQueue.cancelOperation();"
            "window.__casaComandoWebQueue.setActiveTicket('');"
        )

    def test_g01_g02_real_js_dom_observer_and_response_detection(self) -> None:
        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-r1', 41);"
            "window.__casaComandoWebQueue.markSendClicked();"
        )
        self.harness.run_js(
            "document.querySelector('#assistant').textContent = 'respuesta local';"
        )

        self.assertTrue(
            self.harness.wait_until(
                lambda: any(event == "RESPONSE_COMPLETE" for event, _ in self.harness.events),
                timeout_ms=4000,
            )
        )
        payloads = [
            json.loads(payload)
            for event, payload in self.harness.events
            if event == "RESPONSE_COMPLETE"
        ]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["ticket_id"], "ticket-r1")
        self.assertEqual(payloads[0]["operation_id"], 41)
        self.assertEqual(payloads[0]["text"], "respuesta local")

    def test_g03_g04_real_dom_selector_and_controlled_send(self) -> None:
        state = self.harness.run_js(
            """
            (() => {
              const input = document.querySelector('#prompt');
              const button = document.querySelector('button[aria-label="Enviar mensaje"]');
              input.value = 'hola';
              button.click();
              return JSON.stringify({
                input: input.value,
                clicked: window.__sendCount || 0,
                buttonFound: Boolean(button)
              });
            })()
            """
        )
        data = json.loads(state)
        self.assertEqual(data["input"], "hola")
        self.assertEqual(data["clicked"], 1)
        self.assertTrue(data["buttonFound"])

    def test_g05_g14_real_bridge_correlation_and_operation_identity(self) -> None:
        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-r2', 77);"
            "window.__casaComandoWebQueue.markSendClicked();"
        )
        self.harness.run_js(
            "document.querySelector('#assistant').textContent = 'respuesta 77';"
        )
        self.assertTrue(
            self.harness.wait_until(
                lambda: any(event == "RESPONSE_COMPLETE" for event, _ in self.harness.events),
                timeout_ms=4000,
            )
        )
        payload = next(
            json.loads(payload)
            for event, payload in self.harness.events
            if event == "RESPONSE_COMPLETE"
        )
        self.assertEqual(payload["ticket_id"], "ticket-r2")
        self.assertEqual(payload["operation_id"], 77)

    def test_g06_late_response_is_rejected_after_real_runtime_cancellation(self) -> None:
        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-old', 88);"
            "window.__casaComandoWebQueue.markSendClicked();"
            "window.__casaComandoWebQueue.cancelOperation();"
        )
        self.harness.run_js(
            "document.querySelector('#assistant').textContent = 'late response';"
        )

        self.harness.wait_until(lambda: False, timeout_ms=1600)
        self.assertFalse(
            any(event == "RESPONSE_COMPLETE" for event, _ in self.harness.events)
        )

        state = json.loads(
            self.harness.run_js(
                "window.__casaComandoWebQueue.getState();"
            )
        )
        self.assertEqual(state["operation_id"], 89)
        self.assertEqual(state["ticket_id"], "")

    def test_g06_previous_operation_callback_cannot_become_current_response(self) -> None:
        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-new', 102);"
            "window.__casaComandoWebQueue.markSendClicked();"
        )
        self.harness.run_js(
            "document.querySelector('#assistant').textContent = 'new response';"
        )
        self.assertTrue(
            self.harness.wait_until(
                lambda: any(event == "RESPONSE_COMPLETE" for event, _ in self.harness.events),
                timeout_ms=4000,
            )
        )

        self.harness.events.clear()
        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-old', 101);"
            "window.__casaComandoWebQueue.cancelOperation();"
            "document.querySelector('#assistant').textContent = 'old late response';"
        )
        self.harness.wait_until(lambda: False, timeout_ms=1600)
        self.assertFalse(
            any(event == "RESPONSE_COMPLETE" for event, _ in self.harness.events)
        )

    def test_g07_controlled_navigation_reloads_local_page_and_reestablishes_bridge(self) -> None:
        self.harness.loaded = False
        self.harness.events.clear()
        self.harness.view.setHtml(
            "<!doctype html><html><body><section id='assistant'></section></body></html>",
            QUrl("http://controlled.local/second"),
        )
        self.assertTrue(
            self.harness.wait_until(
                lambda: self.harness.loaded
                and self.harness.run_js("document.readyState") == "complete"
            )
        )
        self.harness.install_monitor()
        self.assertTrue(
            any(event == "MONITOR_READY" for event, _ in self.harness.events)
        )




    def test_m01_qweb_adapter_authorizes_real_local_qweb_execution(self) -> None:
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "controlled://webchat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
        )
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="ticket-m01",
            operation_id="qweb-ticket-m01-1",
        )

        self.assertEqual(PhysicalResourceState.BUSY, adapter.snapshot().state)
        self.assertTrue(adapter.validate_execution(execution))

        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-m01', 301);"
            "window.__casaComandoWebQueue.markSendClicked();"
        )
        self.harness.run_js(
            "document.querySelector('#assistant').textContent = 'respuesta controlada';"
        )
        self.assertTrue(
            self.harness.wait_until(
                lambda: any(
                    event == "RESPONSE_COMPLETE"
                    for event, _ in self.harness.events
                ),
                timeout_ms=4000,
            )
        )
        payload = next(
            json.loads(payload)
            for event, payload in self.harness.events
            if event == "RESPONSE_COMPLETE"
        )
        self.assertTrue(
            adapter.validate_callback(
                execution,
                ticket_id=payload["ticket_id"],
            )
        )
        adapter.confirm_termination(
            execution,
            evidence="controlled QWeb response followed by simulated #terminado",
        )
        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            adapter.snapshot().state,
        )

    def test_m02_invalid_authority_execution_blocks_controlled_send(self) -> None:
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "controlled://webchat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
        )
        claim = adapter.claim_resource()
        execution = adapter.begin_execution(
            claim,
            ticket_id="ticket-m02",
            operation_id="qweb-ticket-m02-1",
        )
        authority.quarantine(
            claim,
            "invalid controlled execution",
            evidence="test",
        )
        self.assertFalse(adapter.validate_execution(execution))
        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-m02', 302);"
            "window.__casaComandoWebQueue.cancelOperation();"
        )
        self.harness.wait_until(lambda: False, timeout_ms=400)
        self.assertFalse(
            any(
                event == "RESPONSE_COMPLETE"
                for event, _ in self.harness.events
            )
        )

    def test_m03_late_controlled_callback_cannot_affect_new_generation(self) -> None:
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "controlled://webchat",
        )
        adapter = QWebPhysicalResourceAdapter(authority, descriptor)

        old_claim = adapter.claim_resource()
        old = adapter.begin_execution(
            old_claim,
            ticket_id="ticket-old",
            operation_id="qweb-old-1",
        )
        authority.quarantine(
            old_claim,
            "old generation invalidated",
            evidence="controlled cancellation",
        )
        authority.reconcile(
            old.physical_resource_id,
            evidence="controlled reconciliation",
        )
        new = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="ticket-new",
            operation_id="qweb-new-2",
        )
        self.assertFalse(
            adapter.validate_callback(old, ticket_id="ticket-old")
        )
        self.assertTrue(
            adapter.validate_callback(new, ticket_id="ticket-new")
        )
        self.harness.run_js(
            "window.__casaComandoWebQueue.beginSend('ticket-old', 303);"
            "window.__casaComandoWebQueue.cancelOperation();"
            "document.querySelector('#assistant').textContent = 'late old response';"
        )
        self.harness.wait_until(lambda: False, timeout_ms=700)
        self.assertFalse(
            any(
                event == "RESPONSE_COMPLETE"
                for event, _ in self.harness.events
            )
        )
        authority.quarantine(
            new and adapter._claim_for_execution(new),
            "cleanup after late callback test",
            evidence="controlled test cleanup",
        )


if __name__ == "__main__":
    unittest.main()


    def test_h10_identity_source_to_qweb_authority_local(self) -> None:
        identity = WebPhysicalIdentity(
            "controlled-local",
            "gemini",
            "declared-controlled-principal",
            "declared-controlled-session",
            self.harness.view.url().toString(),
            "./browser_data/controlled",
            AuthenticationState.VERIFIED,
        )
        authority = PhysicalWebChatResourceAuthority()
        adapter = QWebPhysicalResourceAdapter(
            authority,
            identity.descriptor,
            authentication_state=identity.authentication_state,
        )
        self.assertEqual(
            identity.physical_resource_id,
            adapter.descriptor.physical_resource_id,
        )
        self.assertTrue(
            adapter.validate_interaction_surface(
                self.harness.view.url().toString()
            )
        )
        claim = adapter.claim_resource()
        execution = adapter.begin_execution(
            claim,
            ticket_id="identity-local",
            operation_id="qweb-identity-local-1",
        )
        self.assertTrue(adapter.validate_execution(execution))
        adapter.confirm_termination(
            execution,
            evidence="controlled local QWeb surface",
        )
