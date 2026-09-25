# -*- coding: utf-8 -*-
"""Economía local del Café: puntos, precios, gacha y pity sobre SQLite WAL."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from random import SystemRandom
from typing import Callable

from bot_ia.paths import ECONOMY_DB_PATH, PROJECT_ROOT
from bot_ia.persistence.economy import EconomyDatabase, EconomyPersistenceError


POINTS_STARTING_BALANCE = 50
RARITY_PRICES = {"R": 10, "SR": 35, "UR": 100, "SPECIAL": 150}
ORDER_COST_NORMAL = RARITY_PRICES["R"]
ORDER_COST_HIGH = RARITY_PRICES["SPECIAL"]
GACHA_COST = 10
GAME_REWARDS = {"21": 10, "uno": 12, "ppt": 5}
RARITY_WEIGHTS = (("R", 70), ("SR", 25), ("UR", 5))
PITY_SR_LIMIT = 10
PITY_UR_LIMIT = 50

_RANDOM = SystemRandom()


@dataclass(frozen=True, slots=True)
class CafeWallet:
    user_id: str
    points: int = POINTS_STARTING_BALANCE
    pity_sr: int = 0
    pity_ur: int = 0


@dataclass(frozen=True, slots=True)
class GachaResult:
    rarity: str
    points_spent: int
    consolation: str
    pity_sr: int
    pity_ur: int
    affinity_bonus: bool = False


class CafeWalletStore:
    """Store económico compartido entre procesos mediante una única DB SQLite WAL."""

    LEGACY_FILENAME = "cafe_wallets.json"
    MIGRATION_KEY = "legacy:cafe_wallets:v1"

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root).expanduser().resolve() if root is not None else PROJECT_ROOT
        self.path = ECONOMY_DB_PATH if root is None else self.root / "config" / "bot_ia_economy.sqlite3"
        self.legacy_path = self.root / "config" / self.LEGACY_FILENAME
        self.db = EconomyDatabase(self.path)
        self._migrate_legacy()

    def _migrate_legacy(self) -> None:
        with self.db.transaction(immediate=True) as connection:
            migrated = connection.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                (self.MIGRATION_KEY,),
            ).fetchone()
            if migrated is not None:
                return

            if self.legacy_path.is_file():
                try:
                    payload = json.loads(
                        self.legacy_path.read_text(encoding="utf-8")
                    )
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise EconomyPersistenceError(
                        f"Persistencia heredada corrupta: {self.legacy_path}"
                    ) from error
                if not isinstance(payload, dict):
                    raise EconomyPersistenceError(
                        f"Formato heredado inválido: {self.legacy_path}"
                    )

                for user_id, value in payload.items():
                    try:
                        if isinstance(value, dict):
                            points = max(
                                0,
                                int(
                                    value.get(
                                        "points",
                                        POINTS_STARTING_BALANCE,
                                    )
                                ),
                            )
                            pity_sr = max(
                                0,
                                int(value.get("pity_sr", 0)),
                            )
                            pity_ur = max(
                                0,
                                int(value.get("pity_ur", 0)),
                            )
                        else:
                            points = max(0, int(value))
                            pity_sr = 0
                            pity_ur = 0
                    except (TypeError, ValueError) as error:
                        raise EconomyPersistenceError(
                            f"Registro heredado inválido para usuario {user_id!r}"
                        ) from error

                    connection.execute(
                        """
                        INSERT OR IGNORE INTO wallet(
                            user_id, points, pity_sr, pity_ur
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (str(user_id), points, pity_sr, pity_ur),
                    )

            connection.execute(
                """
                INSERT OR REPLACE INTO schema_meta(key, value)
                VALUES (?, ?)
                """,
                (self.MIGRATION_KEY, "complete"),
            )

    @staticmethod
    def _from_row(user_id: str, row: tuple[object, ...] | None) -> CafeWallet:
        if row is None:
            return CafeWallet(
                str(user_id),
                POINTS_STARTING_BALANCE,
                0,
                0,
            )
        return CafeWallet(
            str(user_id),
            max(0, int(row[0])),
            max(0, int(row[1])),
            max(0, int(row[2])),
        )

    def _get_with_connection(
        self,
        connection,
        user_id: str,
    ) -> CafeWallet:
        row = connection.execute(
            "SELECT points, pity_sr, pity_ur FROM wallet WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        return self._from_row(str(user_id), row)

    @staticmethod
    def _ensure_wallet(connection, user_id: str) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO wallet(
                user_id, points, pity_sr, pity_ur
            ) VALUES (?, ?, 0, 0)
            """,
            (str(user_id), POINTS_STARTING_BALANCE),
        )

    def get(self, user_id: str) -> CafeWallet:
        try:
            with self.db.transaction() as connection:
                return self._get_with_connection(connection, str(user_id))
        except (OSError, ValueError, TypeError, EconomyPersistenceError):
            raise
        except Exception as error:
            raise EconomyPersistenceError(
                f"No se pudo leer wallet de {user_id!r}"
            ) from error

    def balance(self, user_id: str) -> int:
        return self.get(user_id).points

    def pity(self, user_id: str) -> tuple[int, int]:
        wallet = self.get(user_id)
        return wallet.pity_sr, wallet.pity_ur

    def credit(self, user_id: str, amount: int) -> CafeWallet:
        amount = max(0, int(amount))
        with self.db.transaction(immediate=True) as connection:
            self._ensure_wallet(connection, str(user_id))
            connection.execute(
                """
                UPDATE wallet
                SET points = points + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (amount, str(user_id)),
            )
            return self._get_with_connection(connection, str(user_id))

    def credit_in_transaction(
        self,
        connection,
        user_id: str,
        amount: int,
    ) -> CafeWallet:
        """Acredita usando la transacción del llamador."""
        amount = max(0, int(amount))
        self._ensure_wallet(connection, str(user_id))
        connection.execute(
            """
            UPDATE wallet
            SET points = points + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (amount, str(user_id)),
        )
        return self._get_with_connection(connection, str(user_id))

    def debit(self, user_id: str, amount: int) -> CafeWallet:
        amount = max(0, int(amount))
        with self.db.transaction(immediate=True) as connection:
            self._ensure_wallet(connection, str(user_id))
            cursor = connection.execute(
                """
                UPDATE wallet
                SET points = points - ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                  AND points >= ?
                """,
                (amount, str(user_id), amount),
            )
            if cursor.rowcount != 1:
                raise ValueError("Puntos del Café insuficientes")
            return self._get_with_connection(connection, str(user_id))

    def debit_in_transaction(
        self,
        connection,
        user_id: str,
        amount: int,
    ) -> CafeWallet:
        """Descuenta de forma atómica usando la transacción del llamador."""
        amount = max(0, int(amount))
        self._ensure_wallet(connection, str(user_id))
        cursor = connection.execute(
            """
            UPDATE wallet
            SET points = points - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND points >= ?
            """,
            (amount, str(user_id), amount),
        )
        if cursor.rowcount != 1:
            raise ValueError("Puntos del Café insuficientes")
        return self._get_with_connection(connection, str(user_id))

    def reward_game(
        self,
        user_id: str,
        game: str,
        *,
        won: bool,
        multiplier: int = 1,
    ) -> CafeWallet:
        if not won:
            return self.get(user_id)
        if multiplier < 1:
            raise ValueError("game reward multiplier must be positive")
        amount = GAME_REWARDS.get(
            str(game).casefold(),
            0,
        ) * int(multiplier)
        return self.credit(user_id, amount)

    def boost_pity_sr(
        self,
        user_id: str,
        amount: int = 1,
    ) -> CafeWallet:
        """Avanza pity SR de forma atómica sin superar el límite de garantía."""
        amount = max(0, int(amount))
        with self.db.transaction(immediate=True) as connection:
            self._ensure_wallet(connection, str(user_id))
            connection.execute(
                """
                UPDATE wallet
                SET pity_sr = MIN(?, pity_sr + ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (PITY_SR_LIMIT - 1, amount, str(user_id)),
            )
            return self._get_with_connection(connection, str(user_id))

    def record_gacha(
        self,
        user_id: str,
        rarity: str,
    ) -> CafeWallet:
        rarity = str(rarity).strip().upper()
        with self.db.transaction(immediate=True) as connection:
            self._ensure_wallet(connection, str(user_id))
            wallet = self._get_with_connection(connection, str(user_id))
            pity_sr = (
                0
                if rarity in {"SR", "UR"}
                else wallet.pity_sr
            )
            pity_ur = (
                0
                if rarity == "UR"
                else wallet.pity_ur
            )
            connection.execute(
                """
                UPDATE wallet
                SET pity_sr = ?,
                    pity_ur = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (pity_sr, pity_ur, str(user_id)),
            )
            return self._get_with_connection(connection, str(user_id))

    def draw_gacha(
        self,
        user_id: str,
        *,
        roll: Callable[[], int] | None = None,
        maid: str = "Cami",
        affinity_level: int = 0,
    ) -> GachaResult:
        """Lanza Gacha completo en una sola transacción BEGIN IMMEDIATE."""
        with self.db.transaction(immediate=True) as connection:
            self._ensure_wallet(connection, str(user_id))
            wallet = self._get_with_connection(connection, str(user_id))
            if wallet.points < GACHA_COST:
                raise ValueError(
                    "Puntos del Café insuficientes para el Gacha"
                )

            next_sr = wallet.pity_sr + 1
            next_ur = wallet.pity_ur + 1

            if next_ur >= PITY_UR_LIMIT:
                rarity = "UR"
            elif next_sr >= PITY_SR_LIMIT:
                rarity = "SR"
            else:
                value = int(
                    (roll or (lambda: _RANDOM.randrange(100)))()
                ) % 100
                if value < 70:
                    rarity = "R"
                elif value < 95:
                    rarity = "SR"
                else:
                    rarity = "UR"

            pity_sr = 0 if rarity in {"SR", "UR"} else next_sr
            pity_ur = 0 if rarity == "UR" else next_ur
            affinity_bonus = (
                rarity == "R"
                and int(affinity_level) >= 5
            )
            if affinity_bonus:
                pity_sr = min(
                    PITY_SR_LIMIT - 1,
                    pity_sr + 1,
                )

            cursor = connection.execute(
                """
                UPDATE wallet
                SET points = points - ?,
                    pity_sr = ?,
                    pity_ur = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                  AND points >= ?
                """,
                (
                    GACHA_COST,
                    pity_sr,
                    pity_ur,
                    str(user_id),
                    GACHA_COST,
                ),
            )
            if cursor.rowcount != 1:
                raise EconomyPersistenceError(
                    "El saldo cambió mientras se resolvía el Gacha"
                )

            consolation = maid_consolation(maid, rarity)
            if affinity_bonus:
                consolation += (
                    " ❤️ Afinidad Lv.5+: ganas +1 progreso hacia "
                    "la garantía SR."
                )
            return GachaResult(
                rarity,
                GACHA_COST,
                consolation,
                pity_sr,
                pity_ur,
                affinity_bonus,
            )


@dataclass(frozen=True, slots=True)
class OrderQuote:
    cost: int
    kind: str
    rarity: str
    can_afford: bool


def normalize_target_rarity(target_rarity: str | None) -> str:
    value = str(target_rarity or "").strip().upper()
    if value in {"R", "SR", "UR"}:
        return value
    return "SPECIAL"


def quote_bebida_order(
    *,
    existing: bool | None = None,
    target_rarity: str | None = None,
    points: int,
) -> OrderQuote:
    if target_rarity is None:
        target = "R" if existing else "SPECIAL"
    else:
        target = normalize_target_rarity(target_rarity)
    cost = RARITY_PRICES[target]
    kind = "clonación" if target != "SPECIAL" else "personalizada"
    return OrderQuote(cost, kind, target, points >= cost)


def purchase_bebida_order(
    store: CafeWalletStore,
    user_id: str,
    *,
    existing: bool | None = None,
    target_rarity: str | None = None,
) -> OrderQuote:
    target = (
        "R"
        if target_rarity is None and existing
        else "SPECIAL"
        if target_rarity is None
        else normalize_target_rarity(target_rarity)
    )
    cost = RARITY_PRICES[target]
    kind = "clonación" if target != "SPECIAL" else "personalizada"
    try:
        store.debit(user_id, cost)
    except ValueError:
        return OrderQuote(
            cost,
            kind,
            target,
            False,
        )
    return OrderQuote(cost, kind, target, True)


def draw_gacha(
    user_id: str,
    store: CafeWalletStore,
    *,
    roll: Callable[[], int] | None = None,
    maid: str = "Cami",
    affinity_level: int = 0,
) -> GachaResult:
    return store.draw_gacha(
        user_id,
        roll=roll,
        maid=maid,
        affinity_level=affinity_level,
    )


def maid_consolation(maid: str, rarity: str) -> str:
    name = maid.strip() or "Cami"
    if rarity == "R":
        if name.casefold() == "cari":
            return (
                f"☕ {name}: ¡No te desanimes! Esta R es sólo el comienzo. "
                "Guarda tus puntos y vuelve a intentarlo."
            )
        return (
            f"☕ {name}: ¡Ánimo, maestro! Salió una R, pero tu próxima "
            "oportunidad puede traer algo especial."
        )
    if rarity == "SR":
        return (
            f"✨ {name}: ¡Buena tirada! Una SR ya es una pieza destacada "
            "de la colección."
        )
    return (
        f"🌟 {name}: ¡UR! Esta tirada fue excepcional. "
        "Guárdala en tu colección."
    )


def pity_text(
    user_id: str,
    store: CafeWalletStore,
    maid: str = "Cami",
) -> str:
    wallet = store.get(user_id)
    name = maid.strip() or "Cami"
    return (
        f"☕ {name}: llevas {wallet.pity_sr}/{PITY_SR_LIMIT} tiradas hacia "
        f"tu SR y {wallet.pity_ur}/{PITY_UR_LIMIT} tiradas hacia tu UR.\n"
        "El contador SR se reinicia con SR/UR; el contador UR se reinicia "
        "con UR."
    )


def economy_price_text() -> str:
    return (
        "☕ PUNTOS DEL CAFÉ\n"
        f"• Bebida R / clonación R: {RARITY_PRICES['R']} puntos\n"
        f"• Bebida SR / clonación SR: {RARITY_PRICES['SR']} puntos\n"
        f"• Bebida UR / clonación UR: {RARITY_PRICES['UR']} puntos\n"
        f"• Bebida Especial (Custom Prompt): "
        f"{RARITY_PRICES['SPECIAL']} puntos\n"
        f"• Gacha: {GACHA_COST} puntos\n"
        f"• Victoria 21: +{GAME_REWARDS['21']} puntos\n"
        f"• Victoria UNO: +{GAME_REWARDS['uno']} puntos\n"
        f"• Victoria PPT: +{GAME_REWARDS['ppt']} puntos"
    )
