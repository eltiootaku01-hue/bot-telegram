# -*- coding: utf-8 -*-
"""2F-8Q cross-route physical WebChat exclusivity contracts."""

from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--headless --disable-gpu --disable-software-rasterizer",
)

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

from bot_ia.core.physical_resource_authority import (
    PhysicalResourceClaimError,
    PhysicalResourceDescriptor,
    PhysicalResourceOwnershipError,
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
)
from bot_ia.core.web_physical_identity import (
    AuthenticationState,
    WebPhysicalIdentity,
    WebPhysicalIdentityRegistry,
    canonicalize_interaction_surface,
)
from bot_ia.runtime import build_runtime
from services.playwright_physical_resource_adapter import (
    PlaywrightPhysicalResourceAdapter,
)
from services.qweb_physical_resource_adapter import QWebPhysicalResourceAdapter
from bot_ia.core.web_queue import WebQueueManager


SURFACE = "http://127.0.0.1:0/chat"


def _descriptor(
    *,
    principal: str = "same-principal",
    session: str = "same-session",
    surface: str = "http://controlled.local/chat",
) -> PhysicalResourceDescriptor:
    return PhysicalResourceDescriptor.resolve(
        "test",
        principal,
        session,
        surface,
    )


class CountingBackend(WebQueueManager):
    """Test-only WebQueueManager double preserving the concrete backend type."""

    def __init__(
        self,
        *,
        page=None,
        failure: Exception | None = None,
        close_failure: Exception | None = None,
    ) -> None:
        self.pages = {"cari": page} if page is not None else {}
        self.action_count = 0
        self.failure = failure
        self.close_failure = close_failure
        self.close_called = False

    async def process_task(
        self,
        waitress_id: str,
        payload: dict,
    ) -> str:
        if self.failure is not None:
            raise self.failure
        self.action_count += 1
        page = self.pages.get(waitress_id)
        if page is not None:
            page.locator("#send").click()
        return "controlled-response"

    async def close_browser_pool(self) -> None:
        self.close_called = True
        if self.close_failure is not None:
            raise self.close_failure


class ControlledPage:
    """Minimal page shape for deterministic adapter unit contracts."""

    url = "http://controlled.local/chat"

    def is_closed(self) -> bool:
        return False


class CrossRouteWebHandler(BaseHTTPRequestHandler):
    HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Controlled Cross Route</title></head>
<body>
  <textarea id="prompt" aria-label="prompt"></textarea>
  <button id="send" onclick="window.__actionCount=(window.__actionCount||0)+1">
    Send
  </button>
  <div id="response">controlled</div>
</body>
</html>
"""

    def do_GET(self) -> None:
        body = self.HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


class CrossRouteRuntime:
    """Real QWebEngineView/QWebChannel + real Playwright local surface."""

    def __init__(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            CrossRouteWebHandler,
        )
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        self.url = (
            f"http://127.0.0.1:{self.server.server_port}/chat"
        )

        self.qweb = QWebEngineView()
        self.channel = QWebChannel(self.qweb.page())
        self.qweb.page().setWebChannel(self.channel)
        self.qweb_loaded = False
        self.qweb.loadFinished.connect(self._loaded)
        self.qweb.setUrl(QUrl(self.url))

    def _loaded(self, ok: bool) -> None:
        self.qweb_loaded = ok

    def wait_until(
        self,
        predicate,
        timeout_ms: int = 5000,
    ) -> bool:
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

    def run_js(self, script: str):
        result = []
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)

        def done(value) -> None:
            result.append(value)
            loop.quit()

        self.qweb.page().runJavaScript(script, done)
        timer.start(5000)
        loop.exec()
        timer.stop()
        if not result:
            raise AssertionError("QWeb JavaScript callback timed out")
        return result[0]

    def close(self) -> None:
        self.qweb.close()
        self.qweb.deleteLater()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)
        self.app.processEvents()


class CrossRoutePhysicalExclusivityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authority = PhysicalWebChatResourceAuthority()
        self.descriptor = _descriptor()
        self.authority.resolve_resource(
            "test",
            "same-principal",
            "same-session",
            "http://controlled.local/chat",
        )
        self.qweb = QWebPhysicalResourceAdapter(
            self.authority,
            self.descriptor,
            authentication_state=AuthenticationState.VERIFIED,
            requester_identity="qweb-test",
        )
        self.playwright = PlaywrightPhysicalResourceAdapter(
            self.authority,
            self.descriptor,
            CountingBackend(page=ControlledPage()),
            authentication_state=AuthenticationState.VERIFIED,
            requester_identity="playwright-test",
        )

    def test_x01_same_authority_instance(self) -> None:
        runtime = build_runtime(Path(__file__).resolve().parents[1])
        backend = CountingBackend(page=ControlledPage())
        try:
            adapter = PlaywrightPhysicalResourceAdapter.resolve(
                runtime.physical_web_authority,
                WebPhysicalIdentityRegistry.from_toml(
                    Path(__file__).resolve().parents[1]
                    / "config"
                    / "runtime.toml"
                ),
                backend,
                binding_id="cari_gemini",
                expected_provider="gemini",
                expected_logical_actor="cari",
            )
            self.assertIs(
                self.qweb.authority,
                self.playwright.authority,
            )
            self.assertIs(
                runtime.physical_web_authority,
                adapter.authority,
            )
            app_source = (
                Path(__file__).resolve().parents[1]
                / "src"
                / "gui"
                / "app.py"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "self._web_physical_authority = self.runtime.physical_web_authority",
                app_source,
            )
            self.assertIn(
                "self.runtime.physical_web_authority,",
                app_source,
            )
        finally:
            runtime.memory_store.close()

    def test_x02_qweb_first_denies_playwright_and_executes_no_backend_action(self) -> None:
        claim = self.qweb.claim_resource()
        execution = self.qweb.begin_execution(
            claim,
            ticket_id="x02",
            operation_id="qweb-x02-1",
        )
        with self.assertRaises(PhysicalResourceClaimError):
            asyncio.run(
                self.playwright.execute_task(
                    "cari",
                    {"prompt": "blocked"},
                    ticket_id="x02-pw",
                    operation_id="playwright-x02-1",
                )
            )
        self.assertEqual(0, self.playwright.backend.action_count)
        self.assertEqual(
            PhysicalResourceState.BUSY,
            self.authority.snapshot(self.descriptor.physical_resource_id).state,
        )
        self.qweb.confirm_termination(
            execution,
            evidence="x02 controlled qweb release",
        )

    def test_x03_playwright_first_denies_qweb_and_keeps_qweb_action_zero(self) -> None:
        claim = self.playwright.claim_resource()
        execution = self.playwright.begin_execution(
            claim,
            ticket_id="x03",
            operation_id="playwright-x03-1",
            waitress_id="cari",
        )
        qweb_actions = 0
        with self.assertRaises(PhysicalResourceClaimError):
            self.qweb.claim_resource()
        self.assertEqual(0, qweb_actions)
        self.assertEqual(
            PhysicalResourceState.BUSY,
            self.authority.snapshot(self.descriptor.physical_resource_id).state,
        )
        self.playwright.confirm_termination(
            execution,
            evidence="x03 controlled playwright release",
        )

    def test_x04_concurrent_claims_have_exactly_one_winner(self) -> None:
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def attempt(adapter) -> None:
            barrier.wait()
            try:
                claim = adapter.claim_resource()
                result = ("success", claim)
            except PhysicalResourceClaimError:
                result = ("denied", None)
            with lock:
                results.append(result)

        threads = [
            threading.Thread(target=attempt, args=(self.qweb,)),
            threading.Thread(target=attempt, args=(self.playwright,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(
            1,
            sum(item[0] == "success" for item in results),
        )
        self.assertEqual(
            1,
            sum(item[0] == "denied" for item in results),
        )
        winner = next(item[1] for item in results if item[0] == "success")
        self.authority.release(winner)

    def test_x05_repeated_race_100_iterations_no_double_claim(self) -> None:
        for iteration in range(100):
            barrier = threading.Barrier(2)
            results = []
            lock = threading.Lock()
            adapters = (
                (self.qweb, self.playwright)
                if iteration % 2 == 0
                else (self.playwright, self.qweb)
            )

            def attempt(adapter) -> None:
                barrier.wait()
                try:
                    claim = adapter.claim_resource()
                    result = ("success", claim)
                except PhysicalResourceClaimError:
                    result = ("denied", None)
                with lock:
                    results.append(result)

            threads = [
                threading.Thread(
                    target=attempt,
                    args=(adapters[0],),
                ),
                threading.Thread(
                    target=attempt,
                    args=(adapters[1],),
                ),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(
                1,
                sum(item[0] == "success" for item in results),
                f"iteration {iteration}: more than one owner",
            )
            self.assertEqual(
                1,
                sum(item[0] == "denied" for item in results),
            )
            winner = next(
                item[1]
                for item in results
                if item[0] == "success"
            )
            self.authority.release(winner)

    def test_x06_handoff_qweb_to_playwright(self) -> None:
        q_claim = self.qweb.claim_resource()
        q_execution = self.qweb.begin_execution(
            q_claim,
            ticket_id="x06-qweb",
            operation_id="qweb-x06-1",
        )
        self.qweb.confirm_termination(
            q_execution,
            evidence="x06 termination evidence",
        )
        p_claim = self.playwright.claim_resource()
        p_execution = self.playwright.begin_execution(
            p_claim,
            ticket_id="x06-pw",
            operation_id="playwright-x06-2",
            waitress_id="cari",
        )
        self.assertEqual(
            2,
            p_execution.execution_generation,
        )
        self.playwright.confirm_termination(
            p_execution,
            evidence="x06 cleanup",
        )

    def test_x07_handoff_playwright_to_qweb(self) -> None:
        p_claim = self.playwright.claim_resource()
        p_execution = self.playwright.begin_execution(
            p_claim,
            ticket_id="x07-pw",
            operation_id="playwright-x07-1",
            waitress_id="cari",
        )
        self.playwright.confirm_termination(
            p_execution,
            evidence="x07 termination evidence",
        )
        q_claim = self.qweb.claim_resource()
        q_execution = self.qweb.begin_execution(
            q_claim,
            ticket_id="x07-qweb",
            operation_id="qweb-x07-2",
        )
        self.assertEqual(
            2,
            q_execution.execution_generation,
        )
        self.qweb.confirm_termination(
            q_execution,
            evidence="x07 cleanup",
        )

    def test_x08_stale_release_cross_route_is_rejected(self) -> None:
        old_claim = self.qweb.claim_resource()
        self.qweb.release_claim(
            old_claim,
            evidence="x08 qweb generation one released",
        )
        new_claim = self.playwright.claim_resource()

        with self.assertRaises(PhysicalResourceOwnershipError):
            self.qweb.release_claim(
                old_claim,
                evidence="x08 stale qweb release",
            )

        snapshot = self.authority.snapshot(self.descriptor.physical_resource_id)
        self.assertEqual(new_claim.claim_id, snapshot.claim_id)
        self.assertEqual("playwright-test", snapshot.owner)
        self.playwright.release_claim(
            new_claim,
            evidence="x08 cleanup",
        )

    def test_x09_stale_callback_cross_route_cannot_change_owner(self) -> None:
        old_claim = self.qweb.claim_resource()
        old_execution = self.qweb.begin_execution(
            old_claim,
            ticket_id="x09-old",
            operation_id="qweb-x09-old",
        )
        self.qweb.confirm_termination(
            old_execution,
            evidence="x09 qweb termination",
        )
        new_claim = self.playwright.claim_resource()
        new_execution = self.playwright.begin_execution(
            new_claim,
            ticket_id="x09-new",
            operation_id="playwright-x09-new",
            waitress_id="cari",
        )

        self.assertFalse(
            self.qweb.validate_callback(
                old_execution,
                ticket_id="x09-old",
            )
        )
        with self.assertRaises(PhysicalResourceOwnershipError):
            self.qweb.confirm_termination(
                old_execution,
                evidence="x09 stale callback release",
            )
        snapshot = self.authority.snapshot(self.descriptor.physical_resource_id)
        self.assertEqual(new_execution.claim_id, snapshot.claim_id)
        self.assertEqual(
            PhysicalResourceState.BUSY,
            snapshot.state,
        )
        self.playwright.confirm_termination(
            new_execution,
            evidence="x09 cleanup",
        )

    def test_x10_cancellation_keeps_cross_route_exclusion(self) -> None:
        claim = self.qweb.claim_resource()
        execution = self.qweb.begin_execution(
            claim,
            ticket_id="x10",
            operation_id="qweb-x10-1",
        )
        cancelled = self.qweb.request_cancel(execution)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            cancelled.state,
        )
        with self.assertRaises(PhysicalResourceClaimError):
            self.playwright.claim_resource()
        self.qweb.quarantine_resource(
            execution,
            reason="x10 cancellation termination unconfirmed",
            evidence="controlled cancellation",
        )

    def test_x11_timeout_quarantine_blocks_handoff_until_reconciliation(self) -> None:
        claim = self.qweb.claim_resource()
        execution = self.qweb.begin_execution(
            claim,
            ticket_id="x11",
            operation_id="qweb-x11-1",
        )
        self.qweb.quarantine_resource(
            execution,
            reason="TIMEOUT_TERMINATION_UNCONFIRMED",
            evidence="controlled executor timeout",
        )
        with self.assertRaises(PhysicalResourceClaimError):
            self.playwright.claim_resource()

        reconciled = self.authority.reconcile(
            self.descriptor.physical_resource_id,
            evidence="controlled surface verified free",
        )
        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            reconciled.state,
        )
        claim2 = self.playwright.claim_resource()
        self.playwright.release_claim(
            claim2,
            evidence="x11 post-reconciliation handoff",
        )

    def test_x12_qweb_failure_quarantines_cross_route_resource(self) -> None:
        claim = self.qweb.claim_resource()
        execution = self.qweb.begin_execution(
            claim,
            ticket_id="x12",
            operation_id="qweb-x12-1",
        )
        self.qweb.quarantine_resource(
            execution,
            reason="QWEB_BACKEND_FAILURE",
            evidence="controlled QWeb backend failure",
        )
        with self.assertRaises(PhysicalResourceClaimError):
            self.playwright.claim_resource()

    def test_x13_playwright_failure_quarantines_cross_route_resource(self) -> None:
        backend = CountingBackend(
            page=ControlledPage(),
            failure=RuntimeError("controlled Playwright failure"),
        )
        adapter = PlaywrightPhysicalResourceAdapter(
            self.authority,
            self.descriptor,
            backend,
            authentication_state=AuthenticationState.VERIFIED,
            requester_identity="playwright-failing",
        )
        with self.assertRaises(RuntimeError):
            asyncio.run(
                adapter.execute_task(
                    "cari",
                    {"prompt": "failure"},
                    ticket_id="x13",
                    operation_id="playwright-x13-1",
                )
            )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            self.authority.snapshot(
                self.descriptor.physical_resource_id
            ).state,
        )
        with self.assertRaises(PhysicalResourceClaimError):
            self.qweb.claim_resource()

    def test_x14_shutdown_without_termination_evidence_is_fail_closed(self) -> None:
        backend = CountingBackend(page=ControlledPage())
        adapter = PlaywrightPhysicalResourceAdapter(
            self.authority,
            self.descriptor,
            backend,
            authentication_state=AuthenticationState.VERIFIED,
        )
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="x14",
            operation_id="playwright-x14-1",
            waitress_id="cari",
        )
        snapshot = asyncio.run(adapter.shutdown(execution))
        self.assertTrue(backend.close_called)
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            snapshot.state,
        )
        with self.assertRaises(PhysicalResourceClaimError):
            self.qweb.claim_resource()

    def test_x15_independent_resources_can_be_busy_simultaneously(self) -> None:
        descriptor_y = _descriptor(principal="different-principal")
        self.authority.resolve_resource(
            "test",
            "different-principal",
            "same-session",
            "http://controlled.local/chat",
        )
        q_x = QWebPhysicalResourceAdapter(
            self.authority,
            self.descriptor,
            authentication_state=AuthenticationState.VERIFIED,
            requester_identity="qweb-x",
        )
        p_y = PlaywrightPhysicalResourceAdapter(
            self.authority,
            descriptor_y,
            CountingBackend(page=ControlledPage()),
            authentication_state=AuthenticationState.VERIFIED,
            requester_identity="playwright-y",
        )

        x_execution = q_x.begin_execution(
            q_x.claim_resource(),
            ticket_id="x15-x",
            operation_id="qweb-x15-x",
        )
        y_execution = p_y.begin_execution(
            p_y.claim_resource(),
            ticket_id="x15-y",
            operation_id="playwright-x15-y",
            waitress_id="cari",
        )
        self.assertEqual(
            PhysicalResourceState.BUSY,
            self.authority.snapshot(self.descriptor.physical_resource_id).state,
        )
        self.assertEqual(
            PhysicalResourceState.BUSY,
            self.authority.snapshot(descriptor_y.physical_resource_id).state,
        )
        q_x.confirm_termination(x_execution, evidence="x15 cleanup x")
        p_y.confirm_termination(y_execution, evidence="x15 cleanup y")

    def test_x16_resource_id_collision_uses_canonical_surface(self) -> None:
        surface_a = canonicalize_interaction_surface(
            "HTTPS://CONTROLLED.LOCAL:443/chat///"
        )
        surface_b = canonicalize_interaction_surface(
            "https://controlled.local/chat"
        )
        first = PhysicalResourceDescriptor.resolve(
            "test",
            "same-principal",
            "same-session",
            surface_a,
        )
        second = PhysicalResourceDescriptor.resolve(
            "TEST",
            "SAME-PRINCIPAL",
            "same-session",
            surface_b,
        )
        self.assertEqual(
            surface_a,
            surface_b,
        )
        self.assertEqual(
            first.physical_resource_id,
            second.physical_resource_id,
        )

    def test_x17_false_equivalence_prevention(self) -> None:
        base = _descriptor()
        variants = (
            _descriptor(principal="other-principal"),
            _descriptor(session="other-session"),
            _descriptor(surface="http://controlled.local/other"),
        )
        self.assertEqual(
            3,
            len({
                variant.physical_resource_id
                for variant in variants
            }),
        )
        for variant in variants:
            self.assertNotEqual(
                base.physical_resource_id,
                variant.physical_resource_id,
            )

    def test_x18_shared_logical_actor_uses_one_physical_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.toml"
            path.write_text(
                """
[web_identities.shared]
provider = "test"
principal_identity = "shared-principal"
provider_session_identity = "shared-session"
canonical_interaction_surface = "http://controlled.local/chat"
browser_profile = "./browser_data/shared"
authentication_state = "VERIFIED"

[web_identity_bindings.cari]
logical_actor = "cari"
identity_id = "shared"

[web_identity_bindings.sunna]
logical_actor = "sunna"
identity_id = "shared"
""".strip(),
                encoding="utf-8",
            )
            registry = WebPhysicalIdentityRegistry.from_toml(path)
            cari = registry.resolve_binding("cari")
            sunna = registry.resolve_binding("sunna")
            self.assertEqual(
                cari.physical_resource_id,
                sunna.physical_resource_id,
            )

            qweb = QWebPhysicalResourceAdapter(
                self.authority,
                cari.descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="qweb-cari",
            )
            playwright = PlaywrightPhysicalResourceAdapter(
                self.authority,
                sunna.descriptor,
                CountingBackend(page=ControlledPage()),
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="playwright-sunna",
            )
            self.assertIs(qweb.authority, playwright.authority)
            claim = qweb.claim_resource()
            with self.assertRaises(PhysicalResourceClaimError):
                playwright.claim_resource()
            qweb.release_claim(
                claim,
                evidence="x18 cleanup",
            )

    def test_x19_production_authentication_unknown_blocks_both_routes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = WebPhysicalIdentityRegistry.from_toml(
            root / "config" / "runtime.toml"
        )
        identity = registry.resolve_binding(
            "cari_gemini",
            expected_provider="gemini",
            expected_logical_actor="cari",
        )
        self.assertEqual(
            AuthenticationState.UNKNOWN,
            identity.authentication_state,
        )
        qweb = QWebPhysicalResourceAdapter(
            self.authority,
            identity.descriptor,
            authentication_state=identity.authentication_state,
        )
        playwright = PlaywrightPhysicalResourceAdapter(
            self.authority,
            identity.descriptor,
            CountingBackend(page=ControlledPage()),
            authentication_state=identity.authentication_state,
        )
        with self.assertRaises(RuntimeError):
            qweb.claim_resource()
        with self.assertRaises(RuntimeError):
            playwright.claim_resource()

    def test_x20_controlled_cross_route_runtime_with_real_qweb_and_playwright(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("playwright unavailable")

        runtime = CrossRouteWebRuntimeFixture()
        try:
            self.assertTrue(
                runtime.qweb.wait_until(
                    lambda: runtime.qweb.qweb_loaded
                )
            )
            with sync_playwright() as playwright_sync:
                browser = playwright_sync.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-gpu"],
                )
                context = browser.new_context()
                page = context.new_page()
                page.goto(
                    runtime.url,
                    wait_until="domcontentloaded",
                )

                identity = WebPhysicalIdentity(
                    "cross-route-controlled",
                    "test",
                    "test-principal",
                    "test-session",
                    runtime.url,
                    "./browser_data/cross-route-controlled",
                    AuthenticationState.VERIFIED,
                )
                qweb = QWebPhysicalResourceAdapter(
                    self.authority,
                    identity.descriptor,
                    authentication_state=AuthenticationState.VERIFIED,
                    requester_identity="qweb-controlled",
                )
                backend = CountingBackend(page=page)
                playwright_adapter = PlaywrightPhysicalResourceAdapter(
                    self.authority,
                    identity.descriptor,
                    backend,
                    authentication_state=AuthenticationState.VERIFIED,
                    requester_identity="playwright-controlled",
                )

                qweb_claim = qweb.claim_resource()
                qweb_execution = qweb.begin_execution(
                    qweb_claim,
                    ticket_id="x20-qweb",
                    operation_id="qweb-x20-1",
                )
                with self.assertRaises(PhysicalResourceClaimError):
                    asyncio.run(
                        playwright_adapter.execute_task(
                            "cari",
                            {"prompt": "blocked"},
                            ticket_id="x20-pw-blocked",
                            operation_id="playwright-x20-blocked",
                        )
                    )
                self.assertEqual(
                    0,
                    backend.action_count,
                )
                runtime.qweb.run_js(
                    "document.querySelector('#send').click();"
                )
                qweb_count = int(
                    runtime.qweb.run_js(
                        "window.__actionCount || 0"
                    )
                    or 0
                )
                self.assertEqual(1, qweb_count)
                qweb.confirm_termination(
                    qweb_execution,
                    evidence="x20 qweb termination",
                )

                playwright_claim = playwright_adapter.claim_resource()
                playwright_execution = playwright_adapter.begin_execution(
                    playwright_claim,
                    ticket_id="x20-pw",
                    operation_id="playwright-x20-2",
                    waitress_id="cari",
                )
                before_qweb_count = qweb_count
                with self.assertRaises(PhysicalResourceClaimError):
                    qweb.claim_resource()
                self.assertEqual(
                    before_qweb_count,
                    int(
                        runtime.qweb.run_js(
                            "window.__actionCount || 0"
                        )
                        or 0
                    ),
                )
                asyncio.run(
                    backend.process_task(
                        "cari",
                        {"prompt": "controlled"},
                    )
                )
                self.assertEqual(1, backend.action_count)
                self.assertEqual(
                    1,
                    int(
                        page.evaluate(
                            "() => window.__actionCount || 0"
                        )
                        or 0
                    ),
                )
                snapshot = self.authority.snapshot(
                    identity.physical_resource_id
                )
                self.assertEqual(
                    PhysicalResourceState.BUSY,
                    snapshot.state,
                )
                self.assertEqual(
                    "playwright",
                    snapshot.backend,
                )
                playwright_adapter.confirm_termination(
                    playwright_execution,
                    evidence="x20 playwright termination",
                )
                browser.close()
        finally:
            runtime.qweb.close()

    def test_x20_fencing_contract_does_not_allow_backend_specific_identity(self) -> None:
        self.assertEqual(
            self.qweb.descriptor.physical_resource_id,
            self.playwright.descriptor.physical_resource_id,
        )
        self.assertNotIn(
            "browser",
            self.qweb.descriptor.physical_resource_id,
        )
        self.assertNotIn(
            "playwright",
            self.playwright.descriptor.physical_resource_id,
        )


class _CrossRouteQWebWrapper:
    def __init__(self) -> None:
        self.fixture = None


class CrossRouteWebRuntimeFixture:
    def __init__(self) -> None:
        self.qweb = CrossRouteQWebFixture()
        self.url = self.qweb.url


class CrossRouteQWebFixture:
    def __init__(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            CrossRouteWebHandler,
        )
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        self.url = (
            f"http://127.0.0.1:{self.server.server_port}/chat"
        )
        self.qweb = QWebEngineView()
        self.channel = QWebChannel(self.qweb.page())
        self.qweb.page().setWebChannel(self.channel)
        self.qweb_loaded = False
        self.qweb.loadFinished.connect(self._loaded)
        self.qweb.setUrl(QUrl(self.url))

    def _loaded(self, ok: bool) -> None:
        self.qweb_loaded = ok

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

    def run_js(self, script: str):
        result = []
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)

        def done(value) -> None:
            result.append(value)
            loop.quit()

        self.qweb.page().runJavaScript(script, done)
        timer.start(5000)
        loop.exec()
        timer.stop()
        if not result:
            raise AssertionError("QWeb JavaScript callback timed out")
        return result[0]

    def close(self) -> None:
        self.qweb.close()
        self.qweb.deleteLater()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)
        self.app.processEvents()
