# -*- coding: utf-8 -*-
"""Playwright physical-resource adapter contracts and controlled runtime."""

from __future__ import annotations

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import asyncio
import tempfile
import threading
import unittest

from bot_ia.core.physical_resource_authority import (
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
)
from bot_ia.core.web_physical_identity import (
    AuthenticationState,
    WebPhysicalIdentityRegistry,
)
from bot_ia.core.web_queue import WebQueueManager
from services.playwright_physical_resource_adapter import (
    PlaywrightPhysicalResourceAdapter,
    PlaywrightPhysicalResourceExecutionError,
    PlaywrightPhysicalResourceIdentityError,
)

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


VALID_CONFIG = """
[web_identities.controlled]
provider = "test"
principal_identity = "test-principal-01"
provider_session_identity = "test-session-01"
canonical_interaction_surface = "http://controlled.local/chat"
browser_profile = "./browser_data/test"
authentication_state = "UNKNOWN"

[web_identity_bindings.controlled]
logical_actor = "cari"
identity_id = "controlled"
"""

CONTROLLED_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Controlled Playwright</title></head>
<body>
  <textarea aria-label="prompt"></textarea>
  <button class="send-button" aria-label="Enviar mensaje"
          onclick="document.querySelector('.model-response-text').textContent =
              document.querySelector('[aria-label=prompt]').value;
              window.__sendCount = (window.__sendCount || 0) + 1;">
    Enviar
  </button>
  <div class="model-response-text"></div>
</body>
</html>
"""


def _registry_identity(
    root: Path,
    *,
    surface: str = "http://controlled.local/chat",
):
    config = root / "runtime.toml"
    config_body = VALID_CONFIG.replace(
        "http://controlled.local/chat",
        surface,
    )
    config.write_text(config_body, encoding="utf-8")
    registry = WebPhysicalIdentityRegistry.from_toml(config)
    return registry.resolve_binding(
        "controlled",
        expected_provider="test",
        expected_logical_actor="cari",
    )


class _ControlledHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = CONTROLLED_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        return


class _FakePage:
    def __init__(self, url: str) -> None:
        self.url = url
        self._closed = False

    def is_closed(self) -> bool:
        return self._closed


class _FakeLocator:
    def __init__(self, backend) -> None:
        self._backend = backend
        self.filled = ""
        self.clicked = 0

    async def fill(self, value: str) -> None:
        self.filled = value

    async def click(self) -> None:
        self.clicked += 1
        await self._backend.run_controlled_operation()

    async def inner_text(self) -> str:
        return "controlled response"


class _FakeBackend(WebQueueManager):
    def __init__(
        self,
        *,
        ignore_physical_stop: bool = False,
    ) -> None:
        self.playwright = None
        self.browser = None
        self.context = None
        self.pages = {"cari": _FakePage("http://controlled.local/chat")}
        self.interaction_counters = {}
        self.selectors = None
        self.headless = True
        self._closing = False
        self.init_called = False
        self.close_called = False
        self.ignore_physical_stop = ignore_physical_stop
        self.operation_started = asyncio.Event()
        self.operation_in_flight = asyncio.Event()
        self.cancel_requested = asyncio.Event()
        self.physical_stop_observed = asyncio.Event()
        self.operation_finished = asyncio.Event()
        self._finish_requested = asyncio.Event()
        self._control_sequence = 0
        self._cancel_sequence = None
        self._finish_sequence = None
        self._active_operation_id = None
        self.physical_work_count = 0
        self.post_cancel_physical_work = 0
        self.locator = _FakeLocator(self)

    async def init_browser_pool(self) -> None:
        self.init_called = True

    async def close_browser_pool(self) -> None:
        self.close_called = True

    def request_physical_stop(self, operation_id: str) -> None:
        if self._active_operation_id != operation_id:
            return
        self._control_sequence += 1
        self._cancel_sequence = self._control_sequence
        self.cancel_requested.set()

    def allow_finish(self) -> None:
        self._control_sequence += 1
        self._finish_sequence = self._control_sequence
        self._finish_requested.set()

    async def run_controlled_operation(self) -> None:
        self._active_operation_id = getattr(
            self,
            "_pending_operation_id",
            None,
        )
        self.operation_started.set()
        self.operation_in_flight.set()

        cancel_wait = asyncio.create_task(
            self.cancel_requested.wait()
        )
        finish_wait = asyncio.create_task(
            self._finish_requested.wait()
        )
        try:
            if (
                not self.cancel_requested.is_set()
                and not self._finish_requested.is_set()
            ):
                await asyncio.wait(
                    {cancel_wait, finish_wait},
                    return_when=asyncio.FIRST_COMPLETED,
                )

            if self._finish_sequence is not None and (
                self._cancel_sequence is None
                or self._finish_sequence < self._cancel_sequence
            ):
                self.physical_work_count += 1
                if self._cancel_sequence is not None:
                    self.post_cancel_physical_work += 0
            elif self._cancel_sequence is not None and not self.ignore_physical_stop:
                self.physical_stop_observed.set()
                return
            else:
                await self._finish_requested.wait()
                self.physical_work_count += 1
                if (
                    self._cancel_sequence is not None
                    and (
                        self._finish_sequence is None
                        or self._cancel_sequence < self._finish_sequence
                    )
                ):
                    self.post_cancel_physical_work += 1
        finally:
            cancel_wait.cancel()
            finish_wait.cancel()
            await asyncio.gather(
                cancel_wait,
                finish_wait,
                return_exceptions=True,
            )
            self.operation_in_flight.clear()
            self.operation_finished.set()

    async def get_active_locator(
        self,
        page,
        selector_key: str,
        *,
        timeout_ms: int = 10_000,
    ):
        return self.locator


class PlaywrightPhysicalResourceAdapterTests(
    unittest.IsolatedAsyncioTestCase
):
    def _adapter(
        self,
        *,
        authentication_state: AuthenticationState = AuthenticationState.VERIFIED,
        page_url: str = "http://controlled.local/chat",
        ignore_physical_stop: bool = False,
    ):
        authority = PhysicalWebChatResourceAuthority()
        backend = _FakeBackend(
            ignore_physical_stop=ignore_physical_stop,
        )
        backend.pages["cari"] = _FakePage(page_url)
        descriptor = authority.resolve_resource(
            "test",
            "test-principal-01",
            "test-session-01",
            "http://controlled.local/chat",
        )
        adapter = PlaywrightPhysicalResourceAdapter(
            authority,
            descriptor,
            backend,
            authentication_state=authentication_state,
        )
        return adapter, authority, backend

    async def test_p01_claim_and_execution_contract(self):
        adapter, authority, _ = self._adapter()
        claim = adapter.claim_resource()
        execution = adapter.begin_execution(
            claim,
            ticket_id="p01",
            operation_id="playwright-p01-1",
            waitress_id="cari",
        )
        snapshot = authority.snapshot(
            adapter.descriptor.physical_resource_id
        )
        self.assertEqual(PhysicalResourceState.BUSY, snapshot.state)
        self.assertEqual(
            claim.execution_generation,
            execution.execution_generation,
        )
        self.assertEqual("playwright", snapshot.backend)
        self.assertEqual("cari", snapshot.waitress_id)

    async def test_p02_invalid_authority_claim_blocks_action(self):
        adapter, authority, backend = self._adapter()
        claim = adapter.claim_resource()
        execution = adapter.begin_execution(
            claim,
            ticket_id="p02",
            operation_id="playwright-p02-1",
            waitress_id="cari",
        )
        authority.quarantine(
            claim,
            "invalid authority claim",
            evidence="controlled test",
        )
        with self.assertRaises(
            PlaywrightPhysicalResourceExecutionError
        ):
            await adapter.send(execution, "blocked")
        self.assertEqual(0, backend.locator.clicked)

    async def test_p03_stale_generation_is_rejected(self):
        adapter, authority, _ = self._adapter()
        old_claim = adapter.claim_resource()
        old = adapter.begin_execution(
            old_claim,
            ticket_id="old",
            operation_id="playwright-old-1",
            waitress_id="cari",
        )
        adapter.quarantine_resource(
            old,
            reason="old generation invalidated",
            evidence="controlled",
        )
        authority.reconcile(
            old.physical_resource_id,
            evidence="controlled reconciliation",
        )
        new_claim = adapter.claim_resource()
        new = adapter.begin_execution(
            new_claim,
            ticket_id="new",
            operation_id="playwright-new-2",
            waitress_id="cari",
        )
        self.assertFalse(adapter.validate_execution(old))
        self.assertTrue(adapter.validate_execution(new))
        with self.assertRaises(
            PlaywrightPhysicalResourceExecutionError
        ):
            await adapter.read_response(old)

    async def test_p04_page_reuse_keeps_generation_fencing(self):
        adapter, _, backend = self._adapter()
        page = backend.pages["cari"]
        first = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="reuse-1",
            operation_id="playwright-reuse-1",
            waitress_id="cari",
        )
        await adapter.send(first, "first")
        adapter.confirm_termination(
            first,
            evidence="controlled completion generation one",
        )
        second = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="reuse-2",
            operation_id="playwright-reuse-2",
            waitress_id="cari",
        )
        self.assertIs(page, backend.pages["cari"])
        await adapter.send(second, "second")
        with self.assertRaises(
            PlaywrightPhysicalResourceExecutionError
        ):
            await adapter.read_response(first)
        self.assertTrue(adapter.validate_execution(second))

    async def test_p05_cancellation_requires_termination_evidence(self):
        adapter, authority, _ = self._adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="p05",
            operation_id="playwright-p05-1",
            waitress_id="cari",
        )
        snapshot = adapter.request_cancel(execution)
        self.assertEqual(PhysicalResourceState.CANCELLING, snapshot.state)
        with self.assertRaises(
            PlaywrightPhysicalResourceExecutionError
        ):
            await adapter.read_response(execution)
        quarantined = adapter.quarantine_resource(
            execution,
            reason="cancelled without physical termination evidence",
        )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            quarantined.state,
        )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            authority.snapshot(
                execution.physical_resource_id
            ).state,
        )

    async def test_p06_context_failure_quarantines(self):
        adapter, authority, backend = self._adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="p06",
            operation_id="playwright-p06-1",
            waitress_id="cari",
        )
        backend.pages["cari"]._closed = True
        with self.assertRaises(
            PlaywrightPhysicalResourceExecutionError
        ):
            await adapter.send(execution, "boom")
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            authority.snapshot(
                adapter.descriptor.physical_resource_id
            ).state,
        )

    async def test_p07_shutdown_without_evidence_quarantines(self):
        adapter, authority, backend = self._adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="p07",
            operation_id="playwright-p07-1",
            waitress_id="cari",
        )
        snapshot = await adapter.shutdown(execution)
        self.assertTrue(backend.close_called)
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            snapshot.state,
        )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            authority.snapshot(
                adapter.descriptor.physical_resource_id
            ).state,
        )

    async def test_p08_identity_surface_mismatch_denied(self):
        adapter, authority, _ = self._adapter(
            page_url="http://controlled.local/other",
        )
        claim = adapter.claim_resource()
        with self.assertRaises(
            PlaywrightPhysicalResourceIdentityError
        ):
            adapter.begin_execution(
                claim,
                ticket_id="p08",
                operation_id="playwright-p08-1",
                waitress_id="cari",
            )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            authority.snapshot(
                adapter.descriptor.physical_resource_id
            ).state,
        )

    async def test_p09_deterministic_identity_from_registry(self):
        with tempfile.TemporaryDirectory() as tmp_a:
            identity_a = _registry_identity(Path(tmp_a))
        with tempfile.TemporaryDirectory() as tmp_b:
            identity_b = _registry_identity(Path(tmp_b))
        self.assertEqual(
            identity_a.physical_resource_id,
            identity_b.physical_resource_id,
        )

    async def test_p10_different_identity_components_change_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = _registry_identity(Path(tmp))
        principal = replace(
            identity,
            principal_identity="test-principal-02",
        )
        session = replace(
            identity,
            provider_session_identity="test-session-02",
        )
        surface = replace(
            identity,
            canonical_interaction_surface="http://controlled.local/other",
        )
        self.assertNotEqual(
            identity.physical_resource_id,
            principal.physical_resource_id,
        )
        self.assertNotEqual(
            identity.physical_resource_id,
            session.physical_resource_id,
        )
        self.assertNotEqual(
            identity.physical_resource_id,
            surface.physical_resource_id,
        )

    async def test_p11_unknown_authentication_blocks_runtime_start(self):
        adapter, _, backend = self._adapter(
            authentication_state=AuthenticationState.UNKNOWN,
        )
        with self.assertRaises(
            PlaywrightPhysicalResourceIdentityError
        ):
            await adapter.initialize_runtime()
        self.assertFalse(backend.init_called)

    async def test_p12_controlled_playwright_runtime(self):
        if async_playwright is None:
            self.skipTest("playwright package unavailable")

        root = Path(__file__).resolve().parents[1]
        manager = WebQueueManager(
            root / "src" / "config" / "selectors.json",
        )
        playwright = await async_playwright().start()
        browser = None
        context = None
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context()
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                _ControlledHandler,
            )
            server_thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )
            server_thread.start()
            surface = (
                f"http://127.0.0.1:{server.server_port}/chat"
            )

            context_page = await context.new_page()
            await context_page.goto(
                surface,
                wait_until="domcontentloaded",
            )
            manager.playwright = playwright
            manager.browser = browser
            manager.context = context
            manager.pages["cari"] = context_page

            with tempfile.TemporaryDirectory() as tmp:
                identity = _registry_identity(
                    Path(tmp),
                    surface=surface,
                )
            verified = replace(
                identity,
                authentication_state=AuthenticationState.VERIFIED,
            )
            authority = PhysicalWebChatResourceAuthority()
            adapter = PlaywrightPhysicalResourceAdapter.from_identity(
                authority,
                verified,
                manager,
            )

            first = adapter.begin_execution(
                adapter.claim_resource(),
                ticket_id="p12-1",
                operation_id="playwright-p12-1",
                waitress_id="cari",
            )
            await adapter.send(first, "hola controlado")
            self.assertEqual(
                "hola controlado",
                await adapter.read_response(first),
            )
            adapter.confirm_termination(
                first,
                evidence="local controlled Playwright completion",
            )

            second = adapter.begin_execution(
                adapter.claim_resource(),
                ticket_id="p12-2",
                operation_id="playwright-p12-2",
                waitress_id="cari",
            )
            await adapter.send(second, "segunda generación")
            self.assertTrue(adapter.validate_execution(second))
            self.assertFalse(
                adapter.validate_callback(
                    first,
                    ticket_id="p12-1",
                    waitress_id="cari",
                )
            )
            adapter.confirm_termination(
                second,
                evidence="local controlled Playwright completion",
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                authority.snapshot(
                    adapter.descriptor.physical_resource_id
                ).state,
            )
        finally:
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
            await playwright.stop()
            if "server" in locals():
                server.shutdown()
                server.server_close()


    async def test_p14_controlled_cancellation_stops_in_flight_work(self):
        adapter, authority, backend = self._adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="p14",
            operation_id="playwright-p14-1",
            waitress_id="cari",
        )
        backend._pending_operation_id = execution.operation_id
        send_task = asyncio.create_task(
            adapter.send(execution, "controlled cancellation")
        )

        await backend.operation_in_flight.wait()
        self.assertTrue(adapter.validate_execution(execution))
        snapshot = adapter.request_cancel(execution)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            snapshot.state,
        )

        await backend.cancel_requested.wait()
        await backend.physical_stop_observed.wait()
        await backend.operation_finished.wait()
        await send_task

        self.assertEqual(0, backend.physical_work_count)
        self.assertEqual(0, backend.post_cancel_physical_work)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            authority.snapshot(
                execution.physical_resource_id,
            ).state,
        )

    async def test_p15_controlled_seam_detects_ignored_stop(self):
        adapter, _, backend = self._adapter(
            ignore_physical_stop=True,
        )
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="p15",
            operation_id="playwright-p15-1",
            waitress_id="cari",
        )
        backend._pending_operation_id = execution.operation_id
        send_task = asyncio.create_task(
            adapter.send(execution, "ignored cancellation")
        )

        await backend.operation_in_flight.wait()
        adapter.request_cancel(execution)
        await backend.cancel_requested.wait()
        backend.allow_finish()
        await backend.operation_finished.wait()
        await send_task

        self.assertEqual(1, backend.physical_work_count)
        self.assertEqual(1, backend.post_cancel_physical_work)
        with self.assertRaises(AssertionError):
            self.assertEqual(
                0,
                backend.post_cancel_physical_work,
                "controlled stop invariant violated",
            )

    async def test_p16_controlled_finish_wins_before_cancel(self):
        adapter, authority, backend = self._adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="p16",
            operation_id="playwright-p16-1",
            waitress_id="cari",
        )
        backend._pending_operation_id = execution.operation_id
        send_task = asyncio.create_task(
            adapter.send(execution, "finish wins")
        )

        await backend.operation_in_flight.wait()
        backend.allow_finish()
        snapshot = adapter.request_cancel(execution)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            snapshot.state,
        )

        await backend.operation_finished.wait()
        await send_task

        self.assertEqual(1, backend.physical_work_count)
        self.assertEqual(0, backend.post_cancel_physical_work)
        self.assertFalse(backend.physical_stop_observed.is_set())
        self.assertEqual(
            1,
            backend._finish_sequence,
        )
        self.assertEqual(
            2,
            backend._cancel_sequence,
        )
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            authority.snapshot(
                execution.physical_resource_id,
            ).state,
        )

    async def test_p13_claim_from_other_resource_is_denied(self):
        adapter, authority, _ = self._adapter()
        other_descriptor = authority.resolve_resource(
            "test",
            "other-principal",
            "other-session",
            "http://controlled.local/chat",
        )
        other_claim = authority.claim(
            other_descriptor.physical_resource_id,
            "playwright-worker",
        )
        with self.assertRaises(
            PlaywrightPhysicalResourceIdentityError
        ):
            adapter.begin_execution(
                other_claim,
                ticket_id="p13",
                operation_id="playwright-p13-1",
                waitress_id="cari",
            )


if __name__ == "__main__":
    unittest.main()
