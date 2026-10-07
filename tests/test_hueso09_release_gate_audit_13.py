# -*- coding: utf-8 -*-
"""HUESO-09-RELEASE-GATE-AUDIT-13 diagnostic contract tests.

These tests are intentionally synthetic. They do not contact Gemini Web or
QWebEngine. Each evidence value below represents a caller-provided string with
provider termination explicitly NOT PROVEN.
"""

from datetime import datetime, timezone
import unittest

from bot_ia.core.physical_lifecycle_reconciliation import (
    PhysicalLifecycleReconciliation,
)
from bot_ia.core.physical_resource_authority import (
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
)
from bot_ia.core.task_engine import TaskEngine
from bot_ia.core.web_physical_identity import AuthenticationState
from services.qweb_physical_resource_adapter import (
    QWebPhysicalResourceAdapter,
)
from services.web_queue import (
    BotTicket,
    _QueueWorker,
)


class Hueso09ReleaseGateAudit13Tests(unittest.TestCase):
    """Prove the current release gate semantics without a real provider."""

    def _qweb_execution(self):
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            provider="controlled-provider",
            authenticated_account_identity="audit-account",
            session_identity="audit-session",
            canonical_interaction_surface="controlled://webchat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
        )
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="audit-ticket",
            operation_id="qweb-audit-1",
        )
        return authority, adapter, execution

    def test_case_01_actual_webqueue_terminated_path_releases_without_provider_proof(self):
        """#terminado path reaches AVAILABLE using only its hardcoded string."""
        authority, adapter, execution = self._qweb_execution()
        worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
            physical_resource_adapter=adapter,
        )
        worker.current_ticket = BotTicket(
            "audit-ticket",
            "Cari",
            "chat",
            "@u",
            "/cafe",
            "hola",
        )
        worker.physical_execution = execution
        worker.awaiting_terminated = True

        # _finish_current() supplies "QWeb #terminado observed".
        worker._finish_current()

        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            authority.snapshot(execution.physical_resource_id).state,
        )

    def test_case_02_stop_disappeared_string_is_accepted(self):
        authority, adapter, execution = self._qweb_execution()
        adapter.request_cancel(execution)

        snapshot = adapter.confirm_termination(
            execution,
            evidence="Stop button disappeared",
        )

        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            snapshot.state,
        )

    def test_case_03_dom_stable_string_is_accepted(self):
        authority, adapter, execution = self._qweb_execution()

        snapshot = adapter.confirm_termination(
            execution,
            evidence="DOM stable 1200ms",
        )

        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            snapshot.state,
        )

    def test_case_04_provider_wording_is_trusted_when_only_string(self):
        authority, adapter, execution = self._qweb_execution()

        snapshot = adapter.confirm_termination(
            execution,
            evidence="provider termination confirmed",
        )

        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            snapshot.state,
        )

    def test_case_05_record_termination_does_not_add_semantic_evidence_gate(self):
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "audit-account",
            "audit-session-reconciliation",
            "controlled://webchat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
        )
        engine = TaskEngine(
            now_provider=lambda: datetime.now(timezone.utc)
        )
        reconciliation = PhysicalLifecycleReconciliation(authority)
        task = engine.create_task(
            "user",
            "webchat",
            task_id="audit-reconciliation",
        )
        task = engine.start_task(task.task_id)
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id=task.task_id,
            operation_id="qweb-audit-reconciliation-1",
        )
        reconciliation.bind_execution(task, adapter, execution)

        record = reconciliation.record_termination(
            task.task_id,
            evidence="DOM stable 1200ms",
        )

        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            record.physical_state,
        )

    def test_case_06_quarantine_reconcile_also_accepts_nonempty_string(self):
        authority, adapter, execution = self._qweb_execution()
        claim = adapter._claim_for_execution(execution)
        authority.quarantine(
            claim,
            "TERMINATION_UNCONFIRMED",
            evidence="provider termination NOT PROVEN",
        )

        snapshot = authority.reconcile(
            execution.physical_resource_id,
            evidence="DOM stable 1200ms",
        )

        self.assertEqual(
            PhysicalResourceState.AVAILABLE,
            snapshot.state,
        )


if __name__ == "__main__":
    unittest.main()
