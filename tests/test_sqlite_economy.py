# -*- coding: utf-8 -*-
"""Pruebas anti-Murphy para la persistencia económica SQLite."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest

from bot_ia.interfaces.cafe_economy import (
    CafeWalletStore,
    GACHA_COST,
    PITY_SR_LIMIT,
    draw_gacha,
)
from bot_ia.interfaces.cafe_vip import VipStore
from bot_ia.interfaces.order_support import ComplaintStore
from bot_ia.persistence.economy import EconomyPersistenceError


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


class SQLiteEconomyTests(unittest.TestCase):
    def test_all_phase3_stores_share_one_wal_database(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            vip = VipStore(root)
            complaints = ComplaintStore(root)

            self.assertEqual(wallet.path, vip.path)
            self.assertEqual(vip.path, complaints.path)
            self.assertTrue(wallet.path.is_file())

            import sqlite3

            connection = sqlite3.connect(wallet.path)
            mode = connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
            application_id = connection.execute(
                "PRAGMA application_id"
            ).fetchone()[0]
            version = connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table'"
                )
            }
            connection.close()

            self.assertEqual("wal", str(mode).lower())
            self.assertNotEqual(0, application_id)
            self.assertEqual(1, version)
            self.assertTrue({"wallet", "vip", "complaints", "schema_meta"} <= tables)

    def test_corrupt_database_fails_closed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "config" / "bot_ia_economy.sqlite3"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"not a sqlite database")

            with self.assertRaises(EconomyPersistenceError):
                CafeWalletStore(root)

    def test_corrupt_legacy_wallet_fails_closed_before_migration(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "config" / "cafe_wallets.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("{broken", encoding="utf-8")

            with self.assertRaises(EconomyPersistenceError):
                CafeWalletStore(root)

    def test_corrupt_legacy_vip_and_complaint_fail_closed_before_migration(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir(parents=True)

            (config / "cafe_vip.json").write_text(
                "{broken",
                encoding="utf-8",
            )
            with self.assertRaises(EconomyPersistenceError):
                VipStore(root)

            (config / "cafe_vip.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (config / "order_complaints.json").write_text(
                "{broken",
                encoding="utf-8",
            )
            with self.assertRaises(EconomyPersistenceError):
                ComplaintStore(root)

    def test_legacy_wallet_and_vip_data_migrate_without_becoming_runtime_authority(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir(parents=True)
            (config / "cafe_wallets.json").write_text(
                json.dumps(
                    {
                        "wallet-user": {
                            "points": 123,
                            "pity_sr": 4,
                            "pity_ur": 8,
                        }
                    }
                ),
                encoding="utf-8",
            )
            (config / "cafe_vip.json").write_text(
                json.dumps(
                    {
                        "vip-user": {
                            "vip": True,
                            "source": "legacy",
                            "donated_stars": 17,
                        }
                    }
                ),
                encoding="utf-8",
            )

            wallet = CafeWalletStore(root)
            vip = VipStore(root)

            self.assertEqual(
                (123, 4, 8),
                (
                    wallet.get("wallet-user").points,
                    wallet.get("wallet-user").pity_sr,
                    wallet.get("wallet-user").pity_ur,
                ),
            )
            self.assertEqual(17, vip.get("vip-user").donated_stars)

            (config / "cafe_wallets.json").write_text(
                "{now-corrupt}",
                encoding="utf-8",
            )
            self.assertEqual(123, wallet.balance("wallet-user"))
            self.assertEqual(17, vip.get("vip-user").donated_stars)

    def test_concurrent_debits_never_overdraft(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            bootstrap = CafeWalletStore(root)
            bootstrap.credit("concurrent", 20)

            def debit_one(_):
                store = CafeWalletStore(root)
                try:
                    store.debit("concurrent", 10)
                    return True
                except ValueError:
                    return False

            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(debit_one, range(12)))

            self.assertEqual(7, sum(results))
            self.assertEqual(9, bootstrap.balance("concurrent"))

    def test_concurrent_credits_are_not_lost(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = CafeWalletStore(root)

            def credit_one(_):
                CafeWalletStore(root).credit("credited", 5)
                return True

            with ThreadPoolExecutor(max_workers=12) as executor:
                list(executor.map(credit_one, range(20)))

            self.assertEqual(150, store.balance("credited"))

    def test_gacha_spend_and_pity_are_one_atomic_operation(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = CafeWalletStore(root)
            store.credit("gacha", GACHA_COST * 12 - 50)

            results = []

            def draw_one(_):
                return draw_gacha(
                    "gacha",
                    CafeWalletStore(root),
                    roll=lambda: 0,
                    maid="Cami",
                )

            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(draw_one, range(12)))

            successful = len(results)
            self.assertEqual(12, successful)
            wallet = store.get("gacha")
            self.assertEqual(0, wallet.points)
            self.assertLessEqual(wallet.pity_sr, PITY_SR_LIMIT - 1)

    def test_concurrent_complaint_resolution_refunds_once(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallet = CafeWalletStore(root)
            complaint_store = ComplaintStore(root)
            complaint = complaint_store.create(
                "refund-user",
                "chat",
                "reembolso",
                points_paid=35,
            )
            registry = _NullRegistry()

            def resolve_one(_):
                try:
                    record = ComplaintStore(root).resolve(
                        complaint.complaint_id,
                        "refund",
                        wallet_store=CafeWalletStore(root),
                        registry=registry,
                    )
                    return record.status
                except ValueError:
                    return "ALREADY_RESOLVED"

            with ThreadPoolExecutor(max_workers=4) as executor:
                statuses = list(executor.map(resolve_one, range(4)))

            self.assertEqual(1, statuses.count("REFUNDED"))
            self.assertEqual(3, statuses.count("ALREADY_RESOLVED"))
            self.assertEqual(85, wallet.balance("refund-user"))


if __name__ == "__main__":
    unittest.main()
