# -*- coding: utf-8 -*-
"""2F-8S application-runtime lifecycle verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from bot_ia.core.physical_lifecycle_reconciliation import (
    ReconciliationStatus,
    PhysicalLifecycleReconciliation,
)
from bot_ia.core.physical_resource_authority import (
    PhysicalReleaseEvidenceType,
    PhysicalResourceClaimError,
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
    _issue_physical_release_evidence,
)
from bot_ia.core.task_engine import TaskState
from bot_ia.core.task_scheduler import (
    TaskRoute,
    WebChatTaskExecutor,
)
from bot_ia.core.web_physical_identity import (
    AuthenticationState,
    WebPhysicalIdentityRegistry,
)
from bot_ia.runtime import build_runtime
from services.playwright_physical_resource_adapter import (
    PlaywrightPhysicalResourceAdapter,
    PlaywrightPhysicalResourceIdentityError,
)
from services.qweb_physical_resource_adapter import QWebPhysicalResourceAdapter
from services.web_queue import WebChatQueueManager

from test_cross_route_physical_resource_exclusivity import (
    CrossRoutePlaywrightWorker,
    CrossRouteQWebFixture,
)


class ProductionRuntimeLifecycle8STests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS",
            "--headless --disable-gpu --disable-software-rasterizer",
        )
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _runtime(self):
        return build_runtime(self.ROOT)

    def _production_identity(self, runtime):
        registry = WebPhysicalIdentityRegistry.from_toml(
            self.ROOT / "config" / "runtime.toml"
        )
        return registry.resolve_binding(
            "cari_gemini",
            expected_provider="gemini",
            expected_logical_actor="cari",
        )

    @staticmethod
    def _termination_evidence(
        adapter,
        execution,
        *,
        observation: str,
    ):
        snapshot = adapter.snapshot()
        return _issue_physical_release_evidence(
            provider=snapshot.provider,
            evidence_type=PhysicalReleaseEvidenceType.TERMINATION,
            physical_resource_id=execution.physical_resource_id,
            claim_id=execution.claim_id,
            execution_generation=execution.execution_generation,
            operation_id=execution.operation_id,
            ticket_id=execution.ticket_id,
            observation=observation,
        )

    def test_s01_application_startup_creates_runtime_lifecycle_components(self):
        runtime = self._runtime()
        try:
            self.assertIsInstance(
                runtime.physical_web_authority,
                PhysicalWebChatResourceAuthority,
            )
            self.assertIsInstance(
                runtime.physical_lifecycle_reconciliation,
                PhysicalLifecycleReconciliation,
            )
            self.assertIs(
                runtime.physical_lifecycle_reconciliation.authority,
                runtime.physical_web_authority,
            )
            listener = runtime.task_engine._lifecycle_listeners[0]
            self.assertEqual(
                runtime.physical_lifecycle_reconciliation,
                listener.__self__,
            )
            self.assertEqual(
                PhysicalLifecycleReconciliation.observe_logical_task,
                listener.__func__,
            )
        finally:
            runtime.memory_store.close()

    def test_s02_one_shared_authority_reaches_real_gui_qweb_and_playwright_wiring(self):
        from gui.app import CommandCenterWindow
        from bot_ia.core.web_queue import WebQueueManager
        from gui.task_orchestrator import TaskOrchestrator

        runtime = self._runtime()
        window = None
        web_queue = None
        try:
            with (
                patch.object(
                    CommandCenterWindow,
                    "_start_platform_health_checks",
                    return_value=None,
                ),
                patch.object(
                    CommandCenterWindow,
                    "_load_web_page",
                    return_value=None,
                ),
            ):
                window = CommandCenterWindow(runtime=runtime)

            self.assertIs(
                runtime.physical_web_authority,
                window._web_physical_authority,
            )
            self.assertIs(
                runtime.physical_web_authority,
                window._web_queue.physical_resource_adapter.authority,
            )
            self.assertIs(
                runtime.task_engine,
                window._web_queue.task_engine,
            )
            self.assertIs(
                runtime.physical_lifecycle_reconciliation,
                window._web_queue.physical_lifecycle_reconciliation,
            )
            self.assertIsInstance(
                window._web_task_executor,
                WebChatTaskExecutor,
            )
            self.assertIs(
                window._web_task_executor,
                runtime.task_scheduler._executors.get(
                    TaskRoute.WEBCHAT
                ),
            )

            web_queue = WebQueueManager()
            orchestrator = TaskOrchestrator(
                web_worker_callback=web_queue.process_task,
                gui_signal_emitter=window.bridge_signal_adapter,
            )
            window.set_async_engine(orchestrator, web_queue)

            self.assertGreaterEqual(
                len(window._playwright_physical_adapters),
                1,
            )
            authority_ids = {
                id(adapter.authority)
                for adapter in window._playwright_physical_adapters.values()
            }
            self.assertEqual({id(runtime.physical_web_authority)}, authority_ids)

            selected = window._playwright_physical_adapters["cari"]
            self.assertEqual(
                AuthenticationState.UNKNOWN,
                selected.authentication_state,
            )
            self.assertIsNone(web_queue.browser)
            with self.assertRaises(
                PlaywrightPhysicalResourceIdentityError
            ):
                asyncio.run(selected.initialize_runtime())
            self.assertIsNone(web_queue.browser)
        finally:
            if window is not None:
                try:
                    asyncio.run(window.shutdown_async_engine())
                finally:
                    window.close()
                    self.app.processEvents()
            elif web_queue is not None:
                asyncio.run(web_queue.close_browser_pool())
            runtime.memory_store.close()

    def test_s03_qweb_controlled_lifecycle_binds_to_application_reconciliation(self):
        runtime = self._runtime()
        fixture = CrossRouteQWebFixture()
        try:
            descriptor = runtime.physical_web_authority.resolve_resource(
                "test",
                "s03-account",
                "s03-session",
                fixture.url,
            )
            adapter = QWebPhysicalResourceAdapter(
                runtime.physical_web_authority,
                descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="s03-qweb",
            )
            task = runtime.task_engine.create_task(
                "s03-user",
                "webchat",
                task_id="s03-qweb",
            )
            task = runtime.task_engine.start_task(task.task_id)
            self.assertTrue(
                fixture.wait_until(lambda: fixture.qweb_loaded)
            )
            claim = adapter.claim_resource()
            execution = adapter.begin_execution(
                claim,
                ticket_id=task.task_id,
                operation_id="s03-qweb-1",
            )
            record = runtime.physical_lifecycle_reconciliation.bind_execution(
                task,
                adapter,
                execution,
            )
            self.assertEqual(TaskState.RUNNING, record.logical_state)
            self.assertEqual(PhysicalResourceState.BUSY, record.physical_state)
            self.assertEqual(
                ReconciliationStatus.ALIGNED,
                record.reconciliation_status,
            )

            completed = runtime.task_engine.complete(task.task_id)
            self.assertEqual(TaskState.COMPLETED, completed.state)
            completed_busy = (
                runtime.physical_lifecycle_reconciliation.get_reconciliation(
                    task.task_id
                )
            )
            self.assertEqual(
                TaskState.COMPLETED,
                completed_busy.logical_state,
            )
            self.assertEqual(
                PhysicalResourceState.BUSY,
                completed_busy.physical_state,
            )
            self.assertEqual(
                ReconciliationStatus.DIVERGED,
                completed_busy.reconciliation_status,
            )

            logical_observation = "#terminado controlled QWeb"
            termination_evidence = self._termination_evidence(
                adapter,
                execution,
                observation="independent synthetic QWeb termination authorization",
            )
            self.assertNotEqual(
                logical_observation,
                termination_evidence.observation,
            )
            terminated = runtime.physical_lifecycle_reconciliation.record_termination(
                task.task_id,
                evidence=termination_evidence,
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                terminated.physical_state,
            )
            self.assertEqual(
                TaskState.COMPLETED,
                terminated.logical_state,
            )
            self.assertEqual(
                ReconciliationStatus.ALIGNED,
                terminated.reconciliation_status,
            )
        finally:
            fixture.close()
            runtime.memory_store.close()

    def test_s04_playwright_controlled_lifecycle_uses_application_authority(self):
        runtime = self._runtime()
        fixture = CrossRouteQWebFixture()
        worker = CrossRoutePlaywrightWorker(
            runtime.physical_web_authority,
            fixture.url,
        )
        try:
            self.assertTrue(fixture.wait_until(lambda: fixture.qweb_loaded))
            worker.start()
            task = runtime.task_engine.create_task(
                "s04-user",
                "webchat",
                task_id="s04-playwright",
            )
            runtime.task_engine.start_task(task.task_id)
            adapter = worker.call(
                lambda adapter, _backend, _page: adapter
            )
            execution = worker.call(
                lambda adapter, _backend, _page: adapter.begin_execution(
                    adapter.claim_resource(),
                    ticket_id=task.task_id,
                    operation_id="s04-playwright-1",
                    waitress_id="cari",
                )
            )
            self.assertIs(adapter.authority, runtime.physical_web_authority)
            bound = runtime.physical_lifecycle_reconciliation.bind_execution(
                task,
                adapter,
                execution,
            )
            self.assertEqual(PhysicalResourceState.BUSY, bound.physical_state)
            worker.call(
                lambda _adapter, backend, _page: backend.process_task(
                    "cari",
                    {"prompt": "s04 controlled"},
                )
            )
            logical_observation = "controlled Playwright completion"
            termination_evidence = self._termination_evidence(
                adapter,
                execution,
                observation="independent synthetic Playwright termination authorization",
            )
            self.assertNotEqual(
                logical_observation,
                termination_evidence.observation,
            )
            record = runtime.physical_lifecycle_reconciliation.record_termination(
                task.task_id,
                evidence=termination_evidence,
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                record.physical_state,
            )
        finally:
            worker.close()
            fixture.close()
            runtime.memory_store.close()

    def test_s05_taskengine_timeout_requests_physical_cancellation(self):
        runtime = self._runtime()
        fixture = CrossRouteQWebFixture()
        try:
            descriptor = runtime.physical_web_authority.resolve_resource(
                "test",
                "s05-account",
                "s05-session",
                fixture.url,
            )
            adapter = QWebPhysicalResourceAdapter(
                runtime.physical_web_authority,
                descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="s05-qweb",
            )
            now = datetime.now(timezone.utc)
            task = runtime.task_engine.create_task(
                "s05-user",
                "webchat",
                task_id="s05-timeout",
                deadline=now + timedelta(seconds=1),
            )
            task = runtime.task_engine.start_task(task.task_id)
            claim = adapter.claim_resource()
            execution = adapter.begin_execution(
                claim,
                ticket_id=task.task_id,
                operation_id="s05-timeout-1",
            )
            runtime.physical_lifecycle_reconciliation.bind_execution(
                task,
                adapter,
                execution,
            )
            runtime.task_engine.check_deadlines(
                now=now + timedelta(seconds=2)
            )
            record = runtime.physical_lifecycle_reconciliation.get_reconciliation(
                task.task_id
            )
            self.assertEqual(TaskState.TIMED_OUT, record.logical_state)
            self.assertEqual(
                PhysicalResourceState.CANCELLING,
                record.physical_state,
            )
            self.assertNotEqual(
                PhysicalResourceState.AVAILABLE,
                record.physical_state,
            )
        finally:
            fixture.close()
            runtime.memory_store.close()

    def test_s06_taskengine_cancellation_converges_to_cancelling_not_available(self):
        runtime = self._runtime()
        fixture = CrossRouteQWebFixture()
        try:
            descriptor = runtime.physical_web_authority.resolve_resource(
                "test",
                "s06-account",
                "s06-session",
                fixture.url,
            )
            adapter = QWebPhysicalResourceAdapter(
                runtime.physical_web_authority,
                descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="s06-qweb",
            )
            task = runtime.task_engine.create_task(
                "s06-user",
                "webchat",
                task_id="s06-cancel",
            )
            runtime.task_engine.start_task(task.task_id)
            execution = adapter.begin_execution(
                adapter.claim_resource(),
                ticket_id=task.task_id,
                operation_id="s06-cancel-1",
            )
            runtime.physical_lifecycle_reconciliation.bind_execution(
                task,
                adapter,
                execution,
            )
            cancelled = runtime.task_engine.cancel(task.task_id)
            self.assertEqual(TaskState.CANCELLED, cancelled.state)
            record = runtime.physical_lifecycle_reconciliation.get_reconciliation(
                task.task_id
            )
            self.assertEqual(
                PhysicalResourceState.CANCELLING,
                record.physical_state,
            )
            self.assertEqual(
                ReconciliationStatus.CANCELLATION_PENDING,
                record.reconciliation_status,
            )
        finally:
            fixture.close()
            runtime.memory_store.close()

    def test_s07_quarantine_blocks_new_runtime_claim_until_reconciliation(self):
        runtime = self._runtime()
        fixture = CrossRouteQWebFixture()
        try:
            descriptor = runtime.physical_web_authority.resolve_resource(
                "test",
                "s07-account",
                "s07-session",
                fixture.url,
            )
            adapter = QWebPhysicalResourceAdapter(
                runtime.physical_web_authority,
                descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="s07-qweb",
            )
            task = runtime.task_engine.create_task(
                "s07-user",
                "webchat",
                task_id="s07-quarantine",
            )
            runtime.task_engine.start_task(task.task_id)
            execution = adapter.begin_execution(
                adapter.claim_resource(),
                ticket_id=task.task_id,
                operation_id="s07-quarantine-1",
            )
            runtime.physical_lifecycle_reconciliation.bind_execution(
                task,
                adapter,
                execution,
            )
            record = runtime.physical_lifecycle_reconciliation.record_backend_failure(
                task.task_id,
                evidence="controlled backend failure",
            )
            self.assertEqual(
                PhysicalResourceState.QUARANTINED,
                record.physical_state,
            )
            with self.assertRaises(PhysicalResourceClaimError):
                adapter.claim_resource()
        finally:
            fixture.close()
            runtime.memory_store.close()

    def test_s08_cross_route_handoff_with_application_authority(self):
        runtime = self._runtime()
        fixture = CrossRouteQWebFixture()
        worker = CrossRoutePlaywrightWorker(
            runtime.physical_web_authority,
            fixture.url,
        )
        try:
            self.assertTrue(fixture.wait_until(lambda: fixture.qweb_loaded))
            worker.start()
            descriptor = runtime.physical_web_authority.resolve_resource(
                "test",
                "test-principal",
                "test-session",
                fixture.url,
            )
            qweb = QWebPhysicalResourceAdapter(
                runtime.physical_web_authority,
                descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="s08-qweb",
            )
            q_claim = qweb.claim_resource()
            q_task = runtime.task_engine.create_task(
                "s08-user-a",
                "webchat",
                task_id="s08-qweb-task",
            )
            runtime.task_engine.start_task(q_task.task_id)
            q_execution = qweb.begin_execution(
                q_claim,
                ticket_id=q_task.task_id,
                operation_id="s08-qweb-1",
            )
            runtime.physical_lifecycle_reconciliation.bind_execution(
                q_task,
                qweb,
                q_execution,
            )

            with self.assertRaises(PhysicalResourceClaimError):
                worker.call(
                    lambda adapter, _backend, _page: adapter.claim_resource()
                )

            qweb_logical_observation = "#terminado controlled QWeb handoff"
            qweb_termination_evidence = self._termination_evidence(
                qweb,
                q_execution,
                observation="independent synthetic QWeb handoff termination authorization",
            )
            self.assertNotEqual(
                qweb_logical_observation,
                qweb_termination_evidence.observation,
            )
            runtime.physical_lifecycle_reconciliation.record_termination(
                q_task.task_id,
                evidence=qweb_termination_evidence,
            )

            p_adapter = worker.call(
                lambda adapter, _backend, _page: adapter
            )
            p_task = runtime.task_engine.create_task(
                "s08-user-b",
                "webchat",
                task_id="s08-playwright-task",
            )
            runtime.task_engine.start_task(p_task.task_id)
            p_execution = worker.call(
                lambda adapter, _backend, _page: adapter.begin_execution(
                    adapter.claim_resource(),
                    ticket_id=p_task.task_id,
                    operation_id="s08-playwright-2",
                    waitress_id="cari",
                )
            )
            runtime.physical_lifecycle_reconciliation.bind_execution(
                p_task,
                p_adapter,
                p_execution,
            )
            worker.call(
                lambda _adapter, backend, _page: backend.process_task(
                    "cari",
                    {"prompt": "s08 handoff"},
                )
            )
            playwright_logical_observation = "controlled Playwright handoff"
            playwright_termination_evidence = self._termination_evidence(
                p_adapter,
                p_execution,
                observation="independent synthetic Playwright handoff termination authorization",
            )
            self.assertNotEqual(
                playwright_logical_observation,
                playwright_termination_evidence.observation,
            )
            p_record = runtime.physical_lifecycle_reconciliation.record_termination(
                p_task.task_id,
                evidence=playwright_termination_evidence,
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                p_record.physical_state,
            )
            self.assertFalse(
                qweb.validate_callback(
                    q_execution,
                    ticket_id=q_task.task_id,
                )
            )
        finally:
            worker.close()
            fixture.close()
            runtime.memory_store.close()

    def test_s09_real_application_window_shutdown_is_idle_and_fail_closed(self):
        from gui.app import CommandCenterWindow
        runtime = self._runtime()
        try:
            with (
                patch.object(
                    CommandCenterWindow,
                    "_start_platform_health_checks",
                    return_value=None,
                ),
                patch.object(
                    CommandCenterWindow,
                    "_load_web_page",
                    return_value=None,
                ),
            ):
                window = CommandCenterWindow(runtime=runtime)
            self.assertIsNotNone(window._web_queue)
            self.assertFalse(window._web_queue.is_busy)
            window.close()
            self.app.processEvents()
            self.assertTrue(window._closing)
        finally:
            runtime.memory_store.close()

    def test_s10_restart_creates_fresh_runtime_authority(self):
        first = self._runtime()
        second = None
        try:
            descriptor = first.physical_web_authority.resolve_resource(
                "test",
                "restart-account",
                "restart-session",
                "http://127.0.0.1/restart",
            )
            claim = first.physical_web_authority.claim(
                descriptor.physical_resource_id,
                "restart-owner",
            )
            self.assertEqual(
                PhysicalResourceState.CLAIMING,
                first.physical_web_authority.snapshot(
                    descriptor.physical_resource_id
                ).state,
            )
            first.memory_store.close()
            second = self._runtime()
            self.assertIsNot(
                first.physical_web_authority,
                second.physical_web_authority,
            )
            second_descriptor = second.physical_web_authority.resolve_resource(
                descriptor.provider,
                descriptor.authenticated_account_identity,
                descriptor.session_identity,
                descriptor.canonical_interaction_surface,
            )
            self.assertEqual(
                descriptor.physical_resource_id,
                second_descriptor.physical_resource_id,
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                second.physical_web_authority.snapshot(
                    second_descriptor.physical_resource_id
                ).state,
            )
            second_claim = second.physical_web_authority.claim(
                second_descriptor.physical_resource_id,
                "restart-owner-new-runtime",
            )
            second.physical_web_authority.release(second_claim)
            first.physical_web_authority.release(claim)
        finally:
            first.memory_store.close()
            if second is not None:
                second.memory_store.close()

    def test_s11_ghost_ownership_is_not_carried_between_runtime_instances(self):
        first = self._runtime()
        second = self._runtime()
        try:
            descriptor = first.physical_web_authority.resolve_resource(
                "test",
                "ghost-account",
                "ghost-session",
                "http://127.0.0.1/ghost",
            )
            first_claim = first.physical_web_authority.claim(
                descriptor.physical_resource_id,
                "ghost-owner-old",
            )
            second_descriptor = second.physical_web_authority.resolve_resource(
                "test",
                "ghost-account",
                "ghost-session",
                "http://127.0.0.1/ghost",
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                second.physical_web_authority.snapshot(
                    second_descriptor.physical_resource_id
                ).state,
            )
            second_claim = second.physical_web_authority.claim(
                second_descriptor.physical_resource_id,
                "ghost-owner-new",
            )
            second.physical_web_authority.release(second_claim)
            first.physical_web_authority.release(first_claim)
        finally:
            first.memory_store.close()
            second.memory_store.close()

    def test_s12_duplicate_authority_detection_in_application_runtime(self):
        from gui.app import CommandCenterWindow

        runtime = self._runtime()
        try:
            with (
                patch.object(
                    CommandCenterWindow,
                    "_start_platform_health_checks",
                    return_value=None,
                ),
                patch.object(
                    CommandCenterWindow,
                    "_load_web_page",
                    return_value=None,
                ),
            ):
                window = CommandCenterWindow(runtime=runtime)
            try:
                authority_ids = {id(runtime.physical_web_authority)}
                self.assertEqual(1, len(authority_ids))
                self.assertIs(
                    window._web_physical_authority,
                    runtime.physical_web_authority,
                )
            finally:
                window.close()
                self.app.processEvents()
        finally:
            runtime.memory_store.close()

    def test_s13_legacy_guard_audit_preserves_non_equivalent_safety_guards(self):
        service = (
            self.ROOT / "src" / "services" / "web_queue.py"
        ).read_text(encoding="utf-8")
        playwright = (
            self.ROOT / "src" / "bot_ia" / "core" / "web_queue.py"
        ).read_text(encoding="utf-8")

        self.assertIn("_WEB_MESA_UNICA = threading.Lock()", service)
        self.assertIn("_WEB_MESA_UNICA.acquire(", service)
        self.assertIn("_WEB_MESA_UNICA.release()", service)
        self.assertIn("physical_resource_adapter", service)

        for token in (
            "PAGE_TIMEOUT_MS",
            "RESPONSE_TIMEOUT_MS",
            "NAVIGATION_TIMEOUT_MS",
            "get_active_locator",
            "soft_reset_page",
            "close_browser_pool",
        ):
            self.assertIn(token, playwright)

        self.assertIn("WEBCHAT_RESOURCE", (
            self.ROOT / "src" / "bot_ia" / "core" / "task_scheduler.py"
        ).read_text(encoding="utf-8"))

        runtime = self._runtime()
        try:
            production = self._production_identity(runtime)
            self.assertEqual(
                AuthenticationState.UNKNOWN,
                production.authentication_state,
            )
            self.assertFalse(production.can_execute_physically)
        finally:
            runtime.memory_store.close()


if __name__ == "__main__":
    unittest.main()
