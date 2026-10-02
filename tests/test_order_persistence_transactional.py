# -*- coding: utf-8 -*-
"""Pruebas de persistencia transaccional e idempotencia de pedidos."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from bot_ia.interfaces.cafe_economy import CafeWalletStore
from bot_ia.interfaces.cafe_orders import BebidaOrderFlow
from bot_ia.interfaces.order_support import (
    ComplaintStore,
    OrderConfirmation,
    OrderStore,
)
from bot_ia.interfaces.telegram import (
    TelegramInputError,
    TelegramOutbound,
    TelegramPoller,
)
from bot_ia.interfaces.telegram_event_ledger import (
    TelegramEventLedger,
    TelegramEventLedgerError,
)
from bot_ia.persistence.economy import (
    APPLICATION_ID,
    EconomyDatabase,
    EconomyPersistenceError,
)


def _build_order(
    *,
    order_id: str = "ORD-ABCDEF1234",
    user_id: str = "user-1",
    cost: int = 35,
    summary: str = "pedido de prueba",
) -> OrderConfirmation:
    return OrderConfirmation(
        order_id=order_id,
        user_id=user_id,
        product_type="Carta TCG",
        destination="🎴 Carta TCG para el Pool",
        rarity="R",
        cost=cost,
        summary=summary,
        resolution="L",
        render_style="Classic Anime",
        prompt_en="test prompt",
    )


def _confirm_in_process(
    root: str,
    order_id: str,
    user_id: str,
) -> tuple[str, bool]:
    order_store = OrderStore(Path(root))
    wallet_store = CafeWalletStore(Path(root))
    result = order_store.confirm_order(
        order_id,
        user_id,
        wallet_store=wallet_store,
    )
    return result.outcome, result.charged


class _NoOpLock:
    def acquire(self) -> None:
        return None

    def release(self) -> None:
        return None


class _FailOnceClaimLedger(TelegramEventLedger):
    def __init__(self, path: Path) -> None:
        self.fail_next_claim = True
        super().__init__(path)

    def claim_events(self, event_ids, *, update_id=None, metadata=""):
        if self.fail_next_claim:
            self.fail_next_claim = False
            raise TelegramEventLedgerError(
                "injected claim failure after business commit"
            )
        return super().claim_events(
            event_ids,
            update_id=update_id,
            metadata=metadata,
        )


class OrderPersistenceTransactionalTests(unittest.TestCase):
    def test_schema_v1_migrates_to_v2_with_orders(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "config" / "bot_ia_economy.sqlite3"
            database.parent.mkdir(parents=True)

            connection = sqlite3.connect(database)
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute("PRAGMA user_version=1")
            connection.executescript(
                """
                CREATE TABLE schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE wallet (
                    user_id TEXT PRIMARY KEY,
                    points INTEGER NOT NULL,
                    pity_sr INTEGER NOT NULL,
                    pity_ur INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE vip (
                    user_id TEXT PRIMARY KEY,
                    vip INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    donated_stars INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE complaints (
                    complaint_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    product_type TEXT NOT NULL,
                    points_paid INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    points_adjustment INTEGER NOT NULL
                );
                """
            )
            connection.commit()
            connection.close()

            EconomyDatabase(database)

            connection = sqlite3.connect(database)
            try:
                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                indexes = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='index'"
                    )
                }
            finally:
                connection.close()

            self.assertEqual(2, version)
            self.assertIn("orders", tables)
            self.assertIn("ux_orders_one_pending_user", indexes)

    def test_telegram_final_selection_persists_pending_before_confirmation(self):
        from bot_ia.interfaces.telegram import TelegramAdapter

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            flow = BebidaOrderFlow()
            flow.start("user-1")
            flow.choose("user-1", "exposure", "SFW")
            flow.choose("user-1", "boldness", "Suave")
            flow.choose("user-1", "product_type", "Carta TCG")
            flow.choose("user-1", "resolution", "L")
            flow.choose("user-1", "render_style", "Classic Anime")

            adapter = TelegramAdapter.__new__(TelegramAdapter)
            adapter._bebida_flow = flow
            adapter._wallet_store = CafeWalletStore(root)
            adapter._order_store = OrderStore(root)
            adapter._pending_orders = {}
            adapter._last_orders = {}

            update = {
                "callback_query": {
                    "from": {"id": "user-1"},
                    "message": {"chat": {"id": "chat-1"}},
                    "data": "bebida:render_style:Classic Anime",
                }
            }
            outbound = adapter.handle_callback(update)
            pending = OrderStore(root).get_pending("user-1")
            self.assertIsNotNone(pending)

            payload = outbound.payload()
            buttons = payload["reply_markup"]["inline_keyboard"][0]
            callback_data = [button["callback_data"] for button in buttons]
            self.assertIn(
                f"order:confirm:{pending.order_id}",
                callback_data,
            )
            self.assertIn(
                f"order:cancel:{pending.order_id}",
                callback_data,
            )

            reopened = OrderStore(root)
            recovered = reopened.get_pending("user-1")
            self.assertEqual(pending, recovered)
            self.assertEqual(
                pending.order_id,
                recovered.order_id,
            )

    def test_pending_survives_restart_and_attachment_metadata_is_recoverable(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            order = _build_order()
            OrderStore(root).create_pending(order)

            reopened = OrderStore(root)
            recovered = reopened.get(order.order_id)
            self.assertEqual(order, recovered)
            self.assertEqual(order, reopened.get_pending(order.user_id))

    def test_confirm_is_atomic_and_uses_persisted_cost(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order(cost=35)
            orders.create_pending(order)

            result = orders.confirm_order(
                order.order_id,
                order.user_id,
                wallet_store=wallet,
            )

            self.assertEqual("CONFIRMED", result.outcome)
            self.assertTrue(result.charged)
            self.assertEqual(65, wallet.balance("user-1"))
            self.assertEqual(order, orders.get(order.order_id))

    def test_insufficient_balance_keeps_pending_without_debit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            orders = OrderStore(root)
            order = _build_order(cost=100)
            orders.create_pending(order)

            result = orders.confirm_order(
                order.order_id,
                order.user_id,
                wallet_store=wallet,
            )

            self.assertEqual("INSUFFICIENT", result.outcome)
            self.assertFalse(result.charged)
            self.assertEqual(50, wallet.balance(order.user_id))
            self.assertEqual(order, orders.get_pending(order.user_id))

    def test_exception_after_debit_rolls_back_wallet_and_order(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)

            original = wallet.debit_in_transaction

            def fail_after_debit(connection, user_id, amount):
                original(connection, user_id, amount)
                raise RuntimeError("injected failure after debit")

            wallet.debit_in_transaction = fail_after_debit

            with self.assertRaisesRegex(
                RuntimeError,
                "injected failure after debit",
            ):
                orders.confirm_order(
                    order.order_id,
                    order.user_id,
                    wallet_store=wallet,
                )

            self.assertEqual(100, wallet.balance(order.user_id))
            self.assertEqual(order, orders.get_pending(order.user_id))
            self.assertIsNone(orders.get_latest_confirmed(order.user_id))

    def test_direct_save_cannot_create_unfunded_confirmed_order(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = OrderStore(root)
            order = _build_order()

            with self.assertRaises(EconomyPersistenceError):
                store.save(order)

            self.assertIsNone(store.get(order.order_id))

    def test_confirmed_replay_does_not_debit_again(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)

            first = orders.confirm_order(
                order.order_id,
                order.user_id,
                wallet_store=wallet,
            )
            second = orders.confirm_order(
                order.order_id,
                order.user_id,
                wallet_store=wallet,
            )

            self.assertEqual("CONFIRMED", first.outcome)
            self.assertTrue(first.charged)
            self.assertEqual("ALREADY_CONFIRMED", second.outcome)
            self.assertFalse(second.charged)
            self.assertEqual(65, wallet.balance(order.user_id))

    def test_two_threads_confirm_same_order_with_one_debit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)

            def confirm_one(_):
                return OrderStore(root).confirm_order(
                    order.order_id,
                    order.user_id,
                    wallet_store=CafeWalletStore(root),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(confirm_one, range(2)))

            self.assertEqual(1, sum(result.charged for result in results))
            self.assertEqual(65, wallet.balance(order.user_id))
            self.assertCountEqual(
                ["CONFIRMED", "ALREADY_CONFIRMED"],
                [result.outcome for result in results],
            )

    def test_two_processes_confirm_same_order_with_one_debit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)

            with ProcessPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        _confirm_in_process,
                        [str(root), str(root)],
                        [order.order_id, order.order_id],
                        [order.user_id, order.user_id],
                    )
                )

            self.assertEqual(1, sum(charged for _, charged in results))
            self.assertEqual(65, CafeWalletStore(root).balance(order.user_id))
            reopened = OrderStore(root)
            self.assertEqual(order.order_id, reopened.get(order.order_id).order_id)


    def test_cancel_is_durable_and_cannot_be_reconfirmed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)

            cancelled = orders.cancel_order(
                order.order_id,
                order.user_id,
            )
            reopened = OrderStore(root)
            confirmed = reopened.confirm_order(
                order.order_id,
                order.user_id,
                wallet_store=CafeWalletStore(root),
            )

            self.assertEqual("CANCELLED", cancelled.outcome)
            self.assertEqual("CANCELLED", confirmed.outcome)
            self.assertEqual(100, wallet.balance(order.user_id))

    def test_unauthorized_and_unknown_confirm_are_side_effect_free(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)

            with self.assertRaises(PermissionError):
                orders.confirm_order(
                    order.order_id,
                    "other-user",
                    wallet_store=wallet,
                )
            with self.assertRaises(ValueError):
                orders.confirm_order(
                    "ORD-1234567890",
                    order.user_id,
                    wallet_store=wallet,
                )

            self.assertEqual(50, wallet.balance(order.user_id))
            self.assertEqual(order, orders.get_pending(order.user_id))

    def test_pending_user_is_not_silently_replaced(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            orders = OrderStore(root)
            first = _build_order()
            second = _build_order(
                order_id="ORD-123456789A",
                summary="otro pedido",
            )
            orders.create_pending(first)

            with self.assertRaisesRegex(ValueError, first.order_id):
                orders.create_pending(second)

            self.assertEqual(first, orders.get_pending(first.user_id))

    def test_legacy_json_import_is_idempotent(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            order = _build_order()
            legacy = root / "config" / "orders.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps([asdict(order)], ensure_ascii=False),
                encoding="utf-8",
            )

            store = OrderStore(root)
            self.assertEqual(1, store.migrate_legacy_json())
            self.assertEqual(0, store.migrate_legacy_json())
            self.assertEqual(order, store.get(order.order_id))

    def test_legacy_json_corruption_fails_closed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "config" / "orders.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("{broken", encoding="utf-8")

            with self.assertRaises(EconomyPersistenceError):
                OrderStore(root).migrate_legacy_json()

    def test_legacy_migration_conflict_rolls_back_prior_imports(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = _build_order(
                order_id="ORD-1111111111",
                summary="first",
            )
            conflicting = _build_order(
                order_id="ORD-2222222222",
                summary="conflicting",
            )
            existing = _build_order(
                order_id=conflicting.order_id,
                summary="different",
            )

            store = OrderStore(root)
            store.create_pending(existing)
            store.cancel_order(existing.order_id, existing.user_id)

            legacy = root / "config" / "orders.json"
            legacy.write_text(
                json.dumps(
                    [
                        {
                            "order_id": first.order_id,
                            "user_id": first.user_id,
                            "product_type": first.product_type,
                            "destination": first.destination,
                            "rarity": first.rarity,
                            "cost": first.cost,
                            "summary": first.summary,
                            "resolution": first.resolution,
                            "render_style": first.render_style,
                            "prompt_en": first.prompt_en,
                        },
                        {
                            "order_id": conflicting.order_id,
                            "user_id": conflicting.user_id,
                            "product_type": conflicting.product_type,
                            "destination": conflicting.destination,
                            "rarity": conflicting.rarity,
                            "cost": conflicting.cost,
                            "summary": conflicting.summary,
                            "resolution": conflicting.resolution,
                            "render_style": conflicting.render_style,
                            "prompt_en": conflicting.prompt_en,
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(EconomyPersistenceError):
                store.migrate_legacy_json()

            self.assertIsNone(store.get(first.order_id))
            self.assertEqual(existing, store.get(existing.order_id))

    def test_complaint_after_restart_uses_confirmed_order_cost(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            order_store = OrderStore(root)
            order = _build_order()
            order_store.create_pending(order)
            order_store.confirm_order(
                order.order_id,
                order.user_id,
                wallet_store=wallet,
            )

            confirmed = OrderStore(root).get_latest_confirmed(order.user_id)
            self.assertEqual(order, confirmed)

            complaint_store = ComplaintStore(root)
            complaint = complaint_store.create(
                order.user_id,
                "chat",
                "reembolso",
                order_id=confirmed.order_id,
                product_type=confirmed.product_type,
                points_paid=confirmed.cost,
            )
            resolved = ComplaintStore(root).resolve(
                complaint.complaint_id,
                "refund",
                wallet_store=CafeWalletStore(root),
                registry=_NullRegistry(),
            )

            self.assertEqual("REFUNDED", resolved.status)
            self.assertEqual(100, CafeWalletStore(root).balance(order.user_id))

    def test_refund_concurrency_credits_once(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)
            orders.confirm_order(
                order.order_id,
                order.user_id,
                wallet_store=wallet,
            )

            complaint = ComplaintStore(root).create(
                order.user_id,
                "chat",
                "reembolso",
                order_id=order.order_id,
                product_type=order.product_type,
                points_paid=order.cost,
            )

            def resolve_one(_):
                try:
                    return ComplaintStore(root).resolve(
                        complaint.complaint_id,
                        "refund",
                        wallet_store=CafeWalletStore(root),
                        registry=_NullRegistry(),
                    ).status
                except ValueError:
                    return "ALREADY_RESOLVED"

            with ThreadPoolExecutor(max_workers=4) as executor:
                statuses = list(executor.map(resolve_one, range(4)))

            self.assertEqual(1, statuses.count("REFUNDED"))
            self.assertEqual(3, statuses.count("ALREADY_RESOLVED"))
            self.assertEqual(100, CafeWalletStore(root).balance(order.user_id))

    def test_telegram_order_callback_uses_order_id_and_enforces_ownership(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            order_store = OrderStore(root)
            order = _build_order()
            order_store.create_pending(order)

            from bot_ia.interfaces.telegram import TelegramAdapter

            telegram_adapter = TelegramAdapter.__new__(TelegramAdapter)
            telegram_adapter._order_store = order_store
            telegram_adapter._wallet_store = wallet
            telegram_adapter._pending_orders = {}
            telegram_adapter._last_orders = {}

            update = {
                "callback_query": {
                    "from": {"id": "user-1"},
                    "message": {
                        "chat": {"id": "chat-1"},
                    },
                    "data": f"order:confirm:{order.order_id}",
                }
            }
            outbound = telegram_adapter.handle_callback(update)
            self.assertIn(order.order_id, outbound.text)
            self.assertEqual(65, wallet.balance(order.user_id))
            self.assertEqual(order, order_store.get(order.order_id))

            unauthorized = {
                "callback_query": {
                    "from": {"id": "other-user"},
                    "message": {
                        "chat": {"id": "chat-1"},
                    },
                    "data": f"order:confirm:{order.order_id}",
                }
            }
            with self.assertRaises(TelegramInputError):
                telegram_adapter.handle_callback(unauthorized)
            self.assertEqual(65, wallet.balance(order.user_id))

    def test_event_replay_after_economic_commit_does_not_double_charge(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            wallet.credit("user-1", 50)
            orders = OrderStore(root)
            order = _build_order()
            orders.create_pending(order)

            update = {
                "update_id": 77,
                "callback_query": {
                    "from": {"id": "user-1"},
                    "message": {
                        "message_id": 9,
                        "chat": {"id": "chat-1"},
                    },
                    "data": f"order:confirm:{order.order_id}",
                },
            }

            class Adapter:
                def handle_update(self, update):
                    data = update["callback_query"]["data"]
                    order_id = data.rsplit(":", 1)[1]
                    result = OrderStore(root).confirm_order(
                        order_id,
                        "user-1",
                        wallet_store=CafeWalletStore(root),
                    )
                    return TelegramOutbound(
                        "chat-1",
                        result.outcome,
                    )

            client = _ClientWithRepeatUpdate(update)
            ledger = _FailOnceClaimLedger(root / "events.sqlite3")
            poller = TelegramPoller(
                client,
                Adapter(),
                event_ledger=ledger,
                sleeper=lambda _: None,
                instance_lock=_NoOpLock(),
            )

            first = poller.run(max_cycles=1)
            self.assertIsNone(poller.offset)
            self.assertEqual(65, wallet.balance("user-1"))
            self.assertEqual(1, len(client.sent))

            second = poller.run(max_cycles=1)
            self.assertEqual(78, poller.offset)
            self.assertEqual(65, wallet.balance("user-1"))
            self.assertEqual(2, len(client.sent))
            reopened = OrderStore(root)
            self.assertEqual(order.order_id, reopened.get(order.order_id).order_id)



class _NullRegistry:
    def record_complaint_balance(
        self,
        user_id,
        complaint_id,
        points_delta,
        status,
        *,
        balance_after=None,
    ):
        return None


class _ClientWithRepeatUpdate:
    token = "test_token"

    def __init__(self, update):
        self.update = update
        self.sent = []
        self.cycles = 0

    def get_updates(self, *, offset=None, timeout_seconds=25):
        self.cycles += 1
        if self.cycles <= 2:
            return (self.update,)
        return ()

    def send(self, outbound):
        self.sent.append(outbound)
        return {"ok": True, "result": {"message_id": len(self.sent)}}


if __name__ == "__main__":
    unittest.main()
