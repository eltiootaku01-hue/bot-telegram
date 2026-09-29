# -*- coding: utf-8 -*-
"""2F-8R logical/physical lifecycle reconciliation tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from bot_ia.core.physical_lifecycle_reconciliation import (
    PhysicalLifecycleReconciliation,
    ReconciliationStatus,
    ReleaseState,
    StaleReconciliationError,
    TerminationState,
)
from bot_ia.core.physical_resource_authority import (
    PhysicalResourceClaim,
    PhysicalResourceClaimError,
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
)
from bot_ia.core.task_engine import (
    ResponseDisposition,
    TaskEngine,
    TaskState,
)
from bot_ia.core.web_physical_identity import AuthenticationState
from bot_ia.runtime import build_runtime
from services.playwright_physical_resource_adapter import (
    PlaywrightPhysicalResourceAdapter,
)
from services.qweb_physical_resource_adapter import QWebPhysicalResourceAdapter

from test_cross_route_physical_resource_exclusivity import (
    CrossRoutePlaywrightWorker,
    CrossRouteRuntime,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(
            2026,
            9,
            29,
            12,
            0,
            tzinfo=timezone.utc,
        )

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


@dataclass(frozen=True)
class FakeExecution:
    physical_resource_id: str
    claim_id: str
    execution_generation: int


class FakePhysicalAdapter:
    """Test-only adapter delegating physical truth to Authority."""

    def __init__(
        self,
        authority: PhysicalWebChatResourceAuthority,
        descriptor,
        *,
        fail_termination: bool = False,
    ) -> None:
        self.authority = authority
        self.descriptor = descriptor
        self.fail_termination = fail_termination
        self.cancel_count = 0

    def snapshot(self):
        return self.authority.snapshot(self.descriptor.physical_resource_id)

    def request_cancel(self, execution: FakeExecution):
        self.cancel_count += 1
        return self.authority.request_cancel(self._claim(execution))

    def confirm_termination(
        self,
        execution: FakeExecution,
        *,
        evidence: str,
    ):
        if self.fail_termination:
            raise RuntimeError("termination evidence rejected")
        return self.authority.release(self._claim(execution))

    def quarantine_resource(
        self,
        execution: FakeExecution,
        *,
        reason: str,
        evidence: str | None = None,
    ):
        return self.authority.quarantine(
            self._claim(execution),
            reason,
            evidence=evidence,
        )

    def _claim(self, execution: FakeExecution) -> PhysicalResourceClaim:
        snapshot = self.authority.snapshot(
            execution.physical_resource_id
        )
        if snapshot.claim_id != execution.claim_id:
            raise RuntimeError("stale fake execution")
        if snapshot.owner is None:
            raise RuntimeError("fake execution has no current owner")
        return PhysicalResourceClaim(
            physical_resource_id=execution.physical_resource_id,
            claim_id=execution.claim_id,
            owner=snapshot.owner,
            execution_generation=execution.execution_generation,
        )


class PhysicalLifecycleReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.authority = PhysicalWebChatResourceAuthority(
            now_provider=self.clock.now,
        )
        self.descriptor = self.authority.resolve_resource(
            "test",
            "recon-account",
            "recon-session",
            "https://controlled.local/chat",
        )
        self.adapter = FakePhysicalAdapter(
            self.authority,
            self.descriptor,
        )
        self.engine = TaskEngine(now_provider=self.clock.now)
        self.reconciliation = PhysicalLifecycleReconciliation(
            self.authority,
        )
        self.engine.add_lifecycle_listener(
            self.reconciliation.observe_logical_task
        )

    def _task(
        self,
        task_id: str = "task-1",
        *,
        deadline=None,
    ):
        task = self.engine.create_task(
            "user",
            "webchat",
            task_id=task_id,
            deadline=deadline,
        )
        self.engine.start_task(task.task_id)
        claim = self.authority.claim(
            self.descriptor.physical_resource_id,
            f"owner-{task_id}",
        )
        self.authority.begin_execution(
            claim,
            backend="test",
            waitress_id="cari",
            operation_id=f"{task_id}:op",
        )
        execution = FakeExecution(
            claim.physical_resource_id,
            claim.claim_id,
            claim.execution_generation,
        )
        self.reconciliation.bind_execution(
            task,
            self.adapter,
            execution,
        )
        return task, execution

    def test_r01_logical_timeout_requests_physical_cancellation(self) -> None:
        task, _ = self._task(
            deadline=self.clock.now() + timedelta(seconds=5)
        )
        self.clock.advance(6)
        self.engine.check_deadlines()
        record = self.reconciliation.get_reconciliation(task.task_id)
        self.assertEqual(TaskState.TIMED_OUT, record.logical_state)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            record.physical_state,
        )
        self.assertEqual(1, self.adapter.cancel_count)

    def test_r02_timed_out_does_not_release_resource(self) -> None:
        task, _ = self._task(
            deadline=self.clock.now() + timedelta(seconds=1)
        )
        self.clock.advance(2)
        self.engine.check_deadlines()
        self.assertNotEqual(
            PhysicalResourceState.AVAILABLE,
            self.authority.snapshot(
                self.descriptor.physical_resource_id
            ).state,
        )
        self.assertEqual(
            ReconciliationStatus.CANCELLATION_PENDING,
            self.reconciliation.get_reconciliation(
                task.task_id
            ).reconciliation_status,
        )

    def test_r03_successful_termination_releases_resource(self) -> None:
        task, _ = self._task()
        record = self.reconciliation.record_termination(
            task.task_id,
            evidence="controlled termination evidence",
        )
        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            record.physical_state,
        )
        self.assertEqual(
            TerminationState.CONFIRMED,
            record.termination_state,
        )
        self.assertEqual(
            ReleaseState.CONFIRMED,
            record.release_state,
        )

    def test_r04_failed_termination_quarantines_resource(self) -> None:
        self.adapter.fail_termination = True
        task, _ = self._task()
        record = self.reconciliation.record_termination(
            task.task_id,
            evidence="controlled failed termination",
        )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            record.physical_state,
        )
        self.assertEqual(
            ReconciliationStatus.QUARANTINED,
            record.reconciliation_status,
        )
        self.assertEqual(
            TerminationState.FAILED,
            record.termination_state,
        )

    def test_r05_logical_cancellation_requests_physical_cancellation(self) -> None:
        task, _ = self._task()
        cancelled = self.engine.cancel(task.task_id)
        self.assertEqual(TaskState.CANCELLED, cancelled.state)
        record = self.reconciliation.get_reconciliation(task.task_id)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            record.physical_state,
        )
        self.assertEqual(1, self.adapter.cancel_count)

    def test_r06_cancelled_does_not_imply_available(self) -> None:
        task, _ = self._task()
        self.engine.cancel(task.task_id)
        self.assertNotEqual(
            PhysicalResourceState.AVAILABLE,
            self.authority.snapshot(
                self.descriptor.physical_resource_id
            ).state,
        )
        self.assertEqual(
            ReconciliationStatus.CANCELLATION_PENDING,
            self.reconciliation.get_reconciliation(
                task.task_id
            ).reconciliation_status,
        )

    def test_r07_late_physical_response_cannot_revive_logical_task(self) -> None:
        task, _ = self._task(
            deadline=self.clock.now() + timedelta(seconds=1)
        )
        self.clock.advance(2)
        self.engine.check_deadlines()
        self.assertEqual(
            ResponseDisposition.DISCARDED,
            self.engine.validate_response(task.task_id),
        )
        self.assertEqual(
            TaskState.TIMED_OUT,
            self.engine.snapshot(task.task_id).state,
        )

    def test_r08_stale_reconciliation_cannot_affect_new_generation(self) -> None:
        old_task, _ = self._task("task-old")
        self.reconciliation.record_quarantine(
            old_task.task_id,
            reason="controlled stale setup",
            evidence="old generation",
        )
        self.authority.reconcile(
            self.descriptor.physical_resource_id,
            evidence="controlled reconciliation",
        )
        new_claim = self.authority.claim(
            self.descriptor.physical_resource_id,
            "owner-task-new",
        )
        self.authority.begin_execution(
            new_claim,
            backend="test",
            waitress_id="cari",
            operation_id="task-new:op",
        )
        with self.assertRaises(StaleReconciliationError):
            self.reconciliation.record_termination(
                old_task.task_id,
                evidence="late old generation evidence",
            )
        self.assertEqual(
            new_claim.claim_id,
            self.authority.snapshot(
                self.descriptor.physical_resource_id
            ).claim_id,
        )

    def test_r09_physical_quarantine_reaches_logical_reconciliation(self) -> None:
        task, execution = self._task()
        record = self.reconciliation.record_quarantine(
            task.task_id,
            reason="controlled backend failure",
            evidence="failure evidence",
        )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            record.physical_state,
        )
        self.assertEqual(
            ReconciliationStatus.QUARANTINED,
            record.reconciliation_status,
        )
        self.assertEqual(task.state, record.logical_state)
        self.assertEqual(
            execution.execution_generation,
            record.execution_generation,
        )

    def test_r10_physical_release_reaches_logical_reconciliation(self) -> None:
        task, _ = self._task()
        record = self.reconciliation.record_release(
            task.task_id,
            evidence="controlled release evidence",
        )
        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            record.physical_state,
        )
        self.assertEqual(
            ReconciliationStatus.ALIGNED,
            record.reconciliation_status,
        )

    def test_r11_backend_failure_converges_to_quarantine(self) -> None:
        task, _ = self._task()
        record = self.reconciliation.record_backend_failure(
            task.task_id,
            evidence="backend exception without termination proof",
        )
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            record.physical_state,
        )
        self.assertEqual(
            ReconciliationStatus.QUARANTINED,
            record.reconciliation_status,
        )

    def test_r12_shutdown_during_busy_requests_cancellation(self) -> None:
        task, _ = self._task()
        record = self.reconciliation.request_physical_cancel(task.task_id)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            record.physical_state,
        )

    def test_r13_shutdown_during_cancelling_is_idempotent(self) -> None:
        task, _ = self._task()
        self.reconciliation.request_physical_cancel(task.task_id)
        self.reconciliation.request_physical_cancel(task.task_id)
        self.assertEqual(1, self.adapter.cancel_count)

    def test_r14_timeout_during_cancellation_keeps_resource_blocked(self) -> None:
        task, _ = self._task(
            deadline=self.clock.now() + timedelta(seconds=1)
        )
        self.engine.begin_cancellation(task.task_id)
        self.clock.advance(2)
        self.engine.check_deadlines()
        record = self.reconciliation.get_reconciliation(task.task_id)
        self.assertEqual(TaskState.CANCELLING, record.logical_state)
        self.assertEqual(
            PhysicalResourceState.CANCELLING,
            record.physical_state,
        )
        self.assertEqual(1, self.adapter.cancel_count)

    def test_r15_cancellation_during_timeout_is_rejected(self) -> None:
        task, _ = self._task(
            deadline=self.clock.now() + timedelta(seconds=1)
        )
        self.clock.advance(2)
        self.engine.check_deadlines()
        self.assertEqual(TaskState.TIMED_OUT, self.engine.snapshot(task.task_id).state)
        with self.assertRaises(RuntimeError):
            self.engine.begin_cancellation(task.task_id)
        self.assertEqual(1, self.adapter.cancel_count)

    def test_r16_multiple_timeout_layers_share_one_physical_request(self) -> None:
        task, _ = self._task(
            deadline=self.clock.now() + timedelta(seconds=1)
        )
        self.clock.advance(2)
        self.engine.check_deadlines()
        self.reconciliation.request_physical_cancel(task.task_id)
        self.reconciliation.request_physical_cancel(task.task_id)
        self.assertEqual(1, self.adapter.cancel_count)

    def test_r17_uncertain_termination_keeps_new_claim_blocked(self) -> None:
        task, execution = self._task()
        self.reconciliation.request_physical_cancel(task.task_id)
        with self.assertRaises(PhysicalResourceClaimError):
            self.authority.claim(
                self.descriptor.physical_resource_id,
                "new-owner",
            )
        self.assertEqual(
            execution.execution_generation,
            self.authority.snapshot(
                self.descriptor.physical_resource_id
            ).execution_generation,
        )

    def test_r18_controlled_qweb_timeout_lifecycle(self) -> None:
        runtime = CrossRouteRuntime()
        try:
            descriptor = self.authority.resolve_resource(
                "test",
                "test-principal",
                "test-session",
                runtime.url,
            )
            qweb = QWebPhysicalResourceAdapter(
                self.authority,
                descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="qweb-r18",
            )
            task = self.engine.create_task(
                "user",
                "webchat",
                task_id="r18-qweb",
                deadline=self.clock.now() + timedelta(seconds=1),
            )
            self.engine.start_task(task.task_id)
            self.assertTrue(
                runtime.wait_until(
                    lambda: runtime.qweb_loaded
                )
            )
            claim = qweb.claim_resource()
            execution = qweb.begin_execution(
                claim,
                ticket_id=task.task_id,
                operation_id="r18-qweb-1",
            )
            self.reconciliation.bind_execution(task, qweb, execution)
            self.clock.advance(2)
            self.engine.check_deadlines()
            self.assertEqual(
                PhysicalResourceState.CANCELLING,
                self.authority.snapshot(
                    descriptor.physical_resource_id
                ).state,
            )
            record = self.reconciliation.record_termination(
                task.task_id,
                evidence="#terminado from controlled QWeb",
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                record.physical_state,
            )
        finally:
            runtime.close()

    def test_r19_controlled_playwright_lifecycle_releases_after_execution(self) -> None:
        runtime = CrossRouteRuntime()
        worker = CrossRoutePlaywrightWorker(
            self.authority,
            runtime.url,
        )
        try:
            self.assertTrue(
                runtime.wait_until(
                    lambda: runtime.qweb_loaded
                )
            )
            worker.start()
            task = self.engine.create_task(
                "user",
                "webchat",
                task_id="r19-playwright",
            )
            self.engine.start_task(task.task_id)
            execution = worker.call(
                lambda adapter, _backend, _page: adapter.begin_execution(
                    adapter.claim_resource(),
                    ticket_id=task.task_id,
                    operation_id="r19-playwright-1",
                    waitress_id="cari",
                )
            )
            adapter = worker.call(
                lambda adapter, _backend, _page: adapter
            )
            self.reconciliation.bind_execution(task, adapter, execution)
            worker.call(
                lambda _adapter, backend, _page: backend.process_task(
                    "cari",
                    {"prompt": "controlled"},
                )
            )
            record = self.reconciliation.record_termination(
                task.task_id,
                evidence="controlled Playwright termination",
            )
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                record.physical_state,
            )
        finally:
            worker.close()
            runtime.close()

    def test_r20_controlled_qweb_playwright_handoff_and_late_generation(self) -> None:
        runtime = CrossRouteRuntime()
        worker = CrossRoutePlaywrightWorker(
            self.authority,
            runtime.url,
        )
        try:
            self.assertTrue(
                runtime.wait_until(
                    lambda: runtime.qweb_loaded
                )
            )
            worker.start()
            descriptor = self.authority.resolve_resource(
                "test",
                "test-principal",
                "test-session",
                runtime.url,
            )
            qweb = QWebPhysicalResourceAdapter(
                self.authority,
                descriptor,
                authentication_state=AuthenticationState.VERIFIED,
                requester_identity="qweb-r20",
            )
            task_a = self.engine.create_task(
                "user",
                "webchat",
                task_id="r20-a",
            )
            task_b = self.engine.create_task(
                "user",
                "webchat",
                task_id="r20-b",
            )
            self.engine.start_task(task_a.task_id)
            self.engine.start_task(task_b.task_id)

            q_claim = qweb.claim_resource()
            q_execution = qweb.begin_execution(
                q_claim,
                ticket_id=task_a.task_id,
                operation_id="r20-qweb-1",
            )
            self.reconciliation.bind_execution(task_a, qweb, q_execution)
            p_adapter = worker.call(
                lambda adapter, _backend, _page: adapter
            )
            self.assertIs(p_adapter.authority, qweb.authority)
            with self.assertRaises(PhysicalResourceClaimError):
                worker.call(
                    lambda adapter, _backend, _page: adapter.claim_resource()
                )

            self.reconciliation.record_termination(
                task_a.task_id,
                evidence="r20 QWeb #terminado",
            )
            self.engine.complete(task_a.task_id)

            p_execution = worker.call(
                lambda adapter, _backend, _page: adapter.begin_execution(
                    adapter.claim_resource(),
                    ticket_id=task_b.task_id,
                    operation_id="r20-playwright-2",
                    waitress_id="cari",
                )
            )
            self.reconciliation.bind_execution(
                task_b,
                p_adapter,
                p_execution,
            )
            worker.call(
                lambda _adapter, backend, _page: backend.process_task(
                    "cari",
                    {"prompt": "controlled"},
                )
            )
            self.assertEqual(
                1,
                worker.call(
                    lambda _adapter, backend, _page: backend.action_count
                ),
            )
            record_b = self.reconciliation.record_termination(
                task_b.task_id,
                evidence="r20 Playwright termination",
            )
            self.engine.complete(task_b.task_id)
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                record_b.physical_state,
            )
            self.assertEqual(
                ReconciliationStatus.ALIGNED,
                self.reconciliation.get_reconciliation(
                    task_b.task_id
                ).reconciliation_status,
            )

            self.assertFalse(
                qweb.validate_callback(
                    q_execution,
                    ticket_id=task_a.task_id,
                )
            )
            self.assertEqual(
                ResponseDisposition.DISCARDED,
                self.engine.validate_response(task_a.task_id),
            )
        finally:
            worker.close()
            runtime.close()


if __name__ == "__main__":
    unittest.main()
