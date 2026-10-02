# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bot_ia.interfaces.telegram import TelegramApiClient, TelegramOutbound, TelegramPoller
from bot_ia.interfaces.telegram_event_ledger import (
    TelegramEventLedger,
    TelegramEventLedgerError,
)
from bot_ia.interfaces.telegram_instance_lock import (
    TelegramInstanceAlreadyRunning,
    TelegramInstanceLock,
)
from bot_ia.interfaces.telegram_outbox import TelegramOutboxStore


class TelegramIntegrityTests(unittest.TestCase):
    def test_event_ledger_claim_is_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = TelegramEventLedger(Path(directory) / "bot_ia_events.sqlite3")
            self.assertTrue(ledger.claim("update_id", "77", update_id=77))
            self.assertFalse(ledger.claim("update_id", "77", update_id=77))
            self.assertTrue(ledger.seen("update_id", "77"))
            self.assertFalse(ledger.completed("update_id", "77"))
            ledger.mark_completed("update_id", "77")
            self.assertTrue(ledger.completed("update_id", "77"))
            self.assertFalse(ledger.claim("update_id", "77", update_id=77))

    def test_payment_charge_id_is_a_separate_idempotency_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = TelegramEventLedger(Path(directory) / "bot_ia_events.sqlite3")
            self.assertTrue(
                ledger.claim(
                    "telegram_payment_charge_id",
                    "charge-123",
                    update_id=9,
                )
            )
            self.assertFalse(
                ledger.claim(
                    "telegram_payment_charge_id",
                    "charge-123",
                    update_id=10,
                )
            )

    def test_multi_key_claim_is_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = TelegramEventLedger(Path(directory) / "events.sqlite3")
            poller = TelegramPoller.__new__(TelegramPoller)
            poller._event_ledger = ledger

            update = {
                "message": {
                    "successful_payment": {
                        "telegram_payment_charge_id": "charge-77",
                    },
                },
            }

            self.assertEqual(
                (True, False),
                poller._claim_event(77, update),
            )
            self.assertEqual(
                "CLAIMED",
                ledger.status("update_id", "77"),
            )
            self.assertEqual(
                "CLAIMED",
                ledger.status(
                    "telegram_payment_charge_id",
                    "charge-77",
                ),
            )
            self.assertEqual(
                (False, True),
                poller._claim_event(77, update),
            )

    def test_multi_key_claim_rolls_back_when_interrupted_between_keys(self) -> None:
        class FaultInjectLedger(TelegramEventLedger):
            def __init__(self, database_path: Path) -> None:
                self.insert_calls = 0
                super().__init__(database_path)

            def _insert_claim(
                self,
                connection,
                event_type,
                event_id,
                *,
                update_id,
                metadata,
                now,
            ) -> None:
                self.insert_calls += 1
                super()._insert_claim(
                    connection,
                    event_type,
                    event_id,
                    update_id=update_id,
                    metadata=metadata,
                    now=now,
                )
                if self.insert_calls == 1:
                    raise RuntimeError("injected interruption between event keys")

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "events.sqlite3"
            ledger = FaultInjectLedger(database)
            poller = TelegramPoller.__new__(TelegramPoller)
            poller._event_ledger = ledger
            update = {
                "message": {
                    "successful_payment": {
                        "telegram_payment_charge_id": "charge-restart",
                    },
                },
            }

            with self.assertRaisesRegex(
                RuntimeError,
                "injected interruption between event keys",
            ):
                poller._claim_event(91, update)

            self.assertIsNone(
                ledger.status("update_id", "91"),
            )
            self.assertIsNone(
                ledger.status(
                    "telegram_payment_charge_id",
                    "charge-restart",
                ),
            )

            restarted = TelegramEventLedger(database)
            poller._event_ledger = restarted

            self.assertEqual(
                (True, False),
                poller._claim_event(91, update),
            )
            self.assertEqual(
                "CLAIMED",
                restarted.status("update_id", "91"),
            )
            self.assertEqual(
                "CLAIMED",
                restarted.status(
                    "telegram_payment_charge_id",
                    "charge-restart",
                ),
            )

    def test_partial_legacy_multi_key_claim_does_not_become_already_seen(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "events.sqlite3"
            ledger = TelegramEventLedger(database)
            ledger.claim("update_id", "92", update_id=92)

            poller = TelegramPoller.__new__(TelegramPoller)
            poller._event_ledger = ledger
            update = {
                "message": {
                    "successful_payment": {
                        "telegram_payment_charge_id": "charge-partial",
                    },
                },
            }

            with self.assertRaises(TelegramEventLedgerError):
                poller._claim_event(92, update)

            self.assertEqual(
                "CLAIMED",
                ledger.status("update_id", "92"),
            )
            self.assertIsNone(
                ledger.status(
                    "telegram_payment_charge_id",
                    "charge-partial",
                ),
            )

    def test_outbox_persists_followups_as_independent_units(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TelegramOutboxStore(Path(directory) / "outbox.sqlite3")
            followups = (
                TelegramOutbound("456", "admin"),
                TelegramOutbound("789", "audit"),
            )
            store.create_pending(
                42,
                TelegramOutbound(
                    "123",
                    "main",
                    followups=followups,
                ),
            )
            created = store.create_followups(42, followups)
            self.assertEqual(2, len(created))
            self.assertEqual(
                ("42:followup:0", "42:followup:1"),
                tuple(item.delivery_id for item in created),
            )
            self.assertFalse(store.all_delivered(42))
            store.mark_followup_delivered("42:followup:0")
            self.assertFalse(store.all_delivered(42))
            store.mark_followup_delivered("42:followup:1")
            self.assertFalse(store.all_delivered(42))
            store.mark_delivered(42)
            self.assertTrue(store.all_delivered(42))

    def test_singleton_lock_rejects_second_owner_and_releases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = TelegramInstanceLock("token-A", Path(directory))
            second = TelegramInstanceLock("token-A", Path(directory))
            first.acquire()
            self.addCleanup(first.release)
            with self.assertRaises(TelegramInstanceAlreadyRunning):
                second.acquire()
            first.release()
            second.acquire()
            second.release()

    def test_polling_duplicate_update_does_not_rerun_adapter_effect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = TelegramEventLedger(Path(directory) / "events.sqlite3")
            batches = [
                [{
                    "update_id": 11,
                    "message": {
                        "from": {"id": 1},
                        "chat": {"id": 2},
                        "text": "hola",
                    },
                }],
                [{
                    "update_id": 11,
                    "message": {
                        "from": {"id": 1},
                        "chat": {"id": 2},
                        "text": "hola",
                    },
                }],
            ]
            sends = []

            def transport(url, payload, timeout):
                if url.endswith("getUpdates"):
                    return {"ok": True, "result": batches.pop(0)}
                sends.append(payload)
                return {"ok": True, "result": {"message_id": len(sends)}}

            client = TelegramApiClient(
                "unused-token",
                transport=transport,
                sleeper=lambda _: None,
            )

            class Adapter:
                def __init__(self):
                    self.calls = 0

                def handle_update(self, _update):
                    self.calls += 1
                    return TelegramOutbound("2", "respuesta")

            adapter = Adapter()
            poller = TelegramPoller(
                client,
                adapter,
                sleeper=lambda _: None,
                event_ledger=ledger,
            )
            first = poller.run(max_cycles=1)
            self.assertEqual(1, first.responses_sent)
            self.assertEqual(1, adapter.calls)

            second = poller.run(max_cycles=1)
            self.assertEqual(0, second.responses_sent)
            self.assertEqual(1, adapter.calls)
