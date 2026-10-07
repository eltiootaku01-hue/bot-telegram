# -*- coding: utf-8 -*-
"""2F-8M contract and QWeb-worker integration tests."""

import unittest

from bot_ia.core.web_physical_identity import AuthenticationState

from bot_ia.core.physical_resource_authority import (
    PhysicalReleaseEvidenceType,
    PhysicalResourceIdentityError,
    PhysicalResourceState,
    PhysicalWebChatResourceAuthority,
    _issue_physical_release_evidence,
)
from services.qweb_physical_resource_adapter import (
    QWebPhysicalResourceAdapter,
)
from services.web_queue import (
    BotTicket,
    _QueueWorker,
    _WEB_MESA_UNICA,
)


def _termination_evidence(adapter, execution, *, observation="controlled termination"):
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


def _sanitization_evidence(adapter, *, observation="controlled sanitization"):
    snapshot = adapter.snapshot()
    return _issue_physical_release_evidence(
        provider=snapshot.provider,
        evidence_type=PhysicalReleaseEvidenceType.SANITIZATION,
        physical_resource_id=snapshot.physical_resource_id,
        claim_id=snapshot.claim_id,
        execution_generation=snapshot.execution_generation,
        operation_id=snapshot.operation_id,
        observation=observation,
    )


def _adapter(authority=None):
    authority = authority or PhysicalWebChatResourceAuthority()
    descriptor = authority.resolve_resource(
        provider="controlled-provider",
        authenticated_account_identity="account-A",
        session_identity="qweb-session-A",
        canonical_interaction_surface="controlled://webchat",
    )
    return QWebPhysicalResourceAdapter(
        authority,
        descriptor,
        authentication_state=AuthenticationState.VERIFIED,
    ), authority


class QWebPhysicalResourceAdapterContractTests(unittest.TestCase):
    def test_q01_identity_is_explicit_and_fail_closed(self):
        authority = PhysicalWebChatResourceAuthority()
        with self.assertRaises(PhysicalResourceIdentityError):
            authority.resolve_resource(
                "controlled-provider",
                "",
                "qweb-session-A",
                "controlled://webchat",
            )

    def test_q02_claim_precedes_physical_execution(self):
        adapter, authority = _adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="ticket-1",
            operation_id="qweb-ticket-1-1",
        )
        snapshot = authority.snapshot(execution.physical_resource_id)
        self.assertEqual(PhysicalResourceState.BUSY, snapshot.state)
        self.assertEqual(
            execution.execution_generation,
            snapshot.execution_generation,
        )

    def test_q03_invalid_claim_blocks_execution(self):
        adapter, authority = _adapter()
        claim = adapter.claim_resource()
        execution = adapter.begin_execution(
            claim,
            ticket_id="ticket-1",
            operation_id="qweb-ticket-1-1",
        )
        authority.quarantine(
            claim,
            "controlled invalidation",
            evidence="test",
        )
        self.assertFalse(adapter.validate_execution(execution))

    def test_q04_stale_claim_blocks_send(self):
        adapter, authority = _adapter()
        first = adapter.claim_resource()
        execution = adapter.begin_execution(
            first,
            ticket_id="old",
            operation_id="qweb-old-1",
        )
        authority.quarantine(
            first,
            "old execution",
            evidence="test",
        )
        authority.reconcile(
            execution.physical_resource_id,
            evidence=_sanitization_evidence(
                adapter,
                observation="controlled reconciliation",
            ),
        )
        second = adapter.claim_resource()
        second_execution = adapter.begin_execution(
            second,
            ticket_id="new",
            operation_id="qweb-new-2",
        )
        self.assertFalse(adapter.validate_execution(execution))
        self.assertTrue(adapter.validate_execution(second_execution))

    def test_q05_valid_claim_permits_execution(self):
        adapter, _ = _adapter()
        claim = adapter.claim_resource()
        execution = adapter.begin_execution(
            claim,
            ticket_id="ticket-valid",
            operation_id="qweb-ticket-valid-1",
        )
        self.assertTrue(adapter.validate_execution(execution))

    def test_q06_generation_is_propagated(self):
        adapter, authority = _adapter()
        claim = adapter.claim_resource()
        execution = adapter.begin_execution(
            claim,
            ticket_id="ticket-generation",
            operation_id="qweb-ticket-generation-1",
        )
        self.assertEqual(claim.execution_generation, execution.execution_generation)
        self.assertEqual(
            execution.execution_generation,
            authority.snapshot(execution.physical_resource_id).execution_generation,
        )

    def test_q07_late_callback_is_rejected(self):
        adapter, authority = _adapter()
        first = adapter.claim_resource()
        old = adapter.begin_execution(
            first,
            ticket_id="ticket-old",
            operation_id="qweb-old-1",
        )
        authority.quarantine(
            first,
            "cancelled",
            evidence="old execution invalidated",
        )
        authority.reconcile(
            old.physical_resource_id,
            evidence=_sanitization_evidence(
                adapter,
                observation="controlled reconciliation",
            ),
        )
        second = adapter.claim_resource()
        new = adapter.begin_execution(
            second,
            ticket_id="ticket-new",
            operation_id="qweb-new-2",
        )
        self.assertFalse(
            adapter.validate_callback(old, ticket_id="ticket-old")
        )
        self.assertTrue(
            adapter.validate_callback(new, ticket_id="ticket-new")
        )
        self.assertEqual(PhysicalResourceState.BUSY, adapter.snapshot().state)

    def test_q08_verified_completion_releases(self):
        adapter, _ = _adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="ticket-complete",
            operation_id="qweb-complete-1",
        )
        snapshot = adapter.confirm_termination(
            execution,
            evidence=_termination_evidence(
                adapter,
                execution,
                observation="controlled #terminado",
            ),
        )
        self.assertEqual(PhysicalResourceState.AVAILABLE, snapshot.state)

    def test_q09_arbitrary_termination_string_is_rejected(self):
        adapter, authority = _adapter()
        execution = adapter.begin_execution(
            adapter.claim_resource(),
            ticket_id="release-reject",
            operation_id="qweb-release-reject-1",
        )
        for evidence in ("arbitrary string", ""):
            with self.assertRaises(Exception):
                adapter.confirm_termination(
                    execution,
                    evidence=evidence,
                )
        self.assertEqual(
            PhysicalResourceState.BUSY,
            authority.snapshot(adapter.descriptor.physical_resource_id).state,
        )

    def test_q10_cancellation_quarantines_without_termination_evidence(self):
        adapter, authority = _adapter()
        worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
            physical_resource_adapter=adapter,
        )
        worker.msg_queue.put(
            BotTicket("cancel", "Cari", "chat", "@u", "/cafe", "hola")
        )
        worker._queued_ids.add("cancel")
        worker._process_next()
        worker.cancel_ticket("cancel")
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            authority.snapshot(adapter.descriptor.physical_resource_id).state,
        )
        self.assertIsNone(worker.physical_execution)
        self.assertFalse(worker.is_busy)

    def test_q11_shutdown_quarantines_busy_resource(self):
        adapter, authority = _adapter()
        worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
            physical_resource_adapter=adapter,
        )
        worker.msg_queue.put(
            BotTicket("shutdown", "Cari", "chat", "@u", "/cafe", "hola")
        )
        worker._queued_ids.add("shutdown")
        worker._process_next()
        worker.stop()
        self.assertEqual(
            PhysicalResourceState.QUARANTINED,
            authority.snapshot(adapter.descriptor.physical_resource_id).state,
        )

    def test_q12_two_qweb_operations_same_resource_do_not_execute(self):
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "controlled://webchat",
        )
        first_adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
            requester_identity="qweb-worker-a",
        )
        second_adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
            requester_identity="qweb-worker-b",
        )
        first = first_adapter.claim_resource()
        first_execution = first_adapter.begin_execution(
            first,
            ticket_id="one",
            operation_id="qweb-one-1",
        )
        with self.assertRaises(RuntimeError):
            second_adapter.claim_resource()
        self.assertTrue(first_adapter.validate_execution(first_execution))

    def test_q13_legacy_mesa_unica_remains_active(self):
        self.assertTrue(_WEB_MESA_UNICA.acquire(blocking=False))
        try:
            adapter, authority = _adapter()
            worker = _QueueWorker(
                timeout_ms=20,
                circuit_threshold=3,
                circuit_cooldown_ms=10000,
                physical_resource_adapter=adapter,
            )
            worker.msg_queue.put(
                BotTicket("legacy-lock", "Cari", "chat", "@u", "/cafe", "hola")
            )
            worker._queued_ids.add("legacy-lock")
            worker._process_next()
            self.assertEqual(
                PhysicalResourceState.AVAILABLE,
                authority.snapshot(adapter.descriptor.physical_resource_id).state,
            )
            self.assertIsNone(worker.physical_execution)
        finally:
            _WEB_MESA_UNICA.release()

    def test_q14_authority_is_independent_from_legacy_lock(self):
        self.assertTrue(_WEB_MESA_UNICA.acquire(blocking=False))
        try:
            adapter, authority = _adapter()
            claim = adapter.claim_resource()
            self.assertEqual(
                PhysicalResourceState.CLAIMING,
                authority.snapshot(adapter.descriptor.physical_resource_id).state,
            )
            adapter.release_claim(
                claim,
                evidence="authority claim tested independently",
            )
        finally:
            _WEB_MESA_UNICA.release()

    def test_q15_worker_exposes_fencing_tuple_before_send_signal(self):
        adapter, authority = _adapter()
        worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
            physical_resource_adapter=adapter,
        )
        observed = []
        worker.web_action_requested.connect(
            lambda kind, ticket_id, prompt: observed.append(
                (
                    kind,
                    ticket_id,
                    worker.physical_execution,
                    authority.snapshot(adapter.descriptor.physical_resource_id),
                )
            )
        )
        worker.msg_queue.put(
            BotTicket("fence", "Cari", "chat", "@u", "/cafe", "hola")
        )
        worker._queued_ids.add("fence")
        worker._process_next()
        self.assertEqual("ticket", observed[0][0])
        self.assertIsNotNone(observed[0][2])
        self.assertEqual(PhysicalResourceState.BUSY, observed[0][3].state)
        self.assertEqual(
            observed[0][2].execution_generation,
            observed[0][3].execution_generation,
        )
        worker._finish_current()


    def test_q16_unknown_authentication_state_blocks_claim(self):
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "https://controlled.local/chat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.UNKNOWN,
        )
        with self.assertRaises(RuntimeError):
            adapter.claim_resource()

    def test_q17_surface_validation_is_canonical_and_fail_closed(self):
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "https://controlled.local/chat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
        )
        self.assertTrue(
            adapter.validate_interaction_surface(
                "HTTPS://CONTROLLED.LOCAL:443/chat/"
            )
        )
        self.assertFalse(
            adapter.validate_interaction_surface(
                "https://different.example/chat"
            )
        )


if __name__ == "__main__":
    unittest.main()


    def test_q14_unknown_authentication_state_blocks_claim(self):
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "https://controlled.local/chat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.UNKNOWN,
        )
        with self.assertRaises(RuntimeError):
            adapter.claim_resource()

    def test_q15_surface_validation_is_canonical_and_fail_closed(self):
        authority = PhysicalWebChatResourceAuthority()
        descriptor = authority.resolve_resource(
            "controlled-provider",
            "account-A",
            "qweb-session-A",
            "https://controlled.local/chat",
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            descriptor,
            authentication_state=AuthenticationState.VERIFIED,
        )
        self.assertTrue(
            adapter.validate_interaction_surface(
                "HTTPS://CONTROLLED.LOCAL:443/chat/"
            )
        )
        self.assertFalse(
            adapter.validate_interaction_surface(
                "https://different.example/chat"
            )
        )
