# -*- coding: utf-8 -*-
"""Confirmación de pedidos y gestión persistente de quejas/reembolsos."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import re
import sqlite3
from typing import TYPE_CHECKING, Literal

from bot_ia.paths import ECONOMY_DB_PATH, PROJECT_ROOT
from bot_ia.persistence.economy import EconomyDatabase, EconomyPersistenceError
from .cafe_economy import CafeWalletStore
if TYPE_CHECKING:
    from gui.waifu_registry import WaifuRegistry

ComplaintAction = Literal["refund", "convert_image", "reject"]
ORDER_ID_PATTERN = re.compile(r"^ORD-[0-9A-F]{10}$")


@dataclass(frozen=True, slots=True)
class OrderConfirmation:
    """Snapshot inmutable que debe confirmarse antes de cobrar."""

    order_id: str
    user_id: str
    product_type: str
    destination: str
    rarity: str
    cost: int
    summary: str
    resolution: str = "L"
    render_style: str = "Classic Anime"
    prompt_en: str = ""


@dataclass(frozen=True, slots=True)
class ComplaintRecord:
    complaint_id: str
    user_id: str
    chat_id: str
    text: str
    order_id: str
    product_type: str
    points_paid: int
    status: str = "OPEN"
    action: str = ""
    created_at: str = ""


class PendingOrderExistsError(ValueError):
    """El usuario ya tiene un pedido PENDING y no se debe reemplazar."""

    def __init__(self, order: OrderConfirmation) -> None:
        self.order = order
        super().__init__(
            f"El usuario ya tiene un pedido pendiente: {order.order_id}"
        )


@dataclass(frozen=True, slots=True)
class OrderConfirmResult:
    order: OrderConfirmation
    outcome: Literal["CONFIRMED", "ALREADY_CONFIRMED", "INSUFFICIENT", "CANCELLED"]
    charged: bool = False


class OrderStore:
    """Repositorio SQLite autoritativo para pedidos."""

    LEGACY_FILENAME = "orders.json"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.db_path = (
            ECONOMY_DB_PATH
            if self.root == PROJECT_ROOT
            else self.root / "config" / "bot_ia_economy.sqlite3"
        )
        self.legacy_path = self.root / "config" / self.LEGACY_FILENAME
        self.path = self.legacy_path
        self.db = EconomyDatabase(self.db_path)

    @staticmethod
    def _from_row(
        row: sqlite3.Row | tuple[object, ...],
    ) -> tuple[OrderConfirmation, str, str, str]:
        return (
            OrderConfirmation(
                order_id=str(row[0]),
                user_id=str(row[1]),
                product_type=str(row[2]),
                destination=str(row[3]),
                rarity=str(row[4]),
                cost=int(row[5]),
                summary=str(row[6]),
                resolution=str(row[7]),
                render_style=str(row[8]),
                prompt_en=str(row[9]),
            ),
            str(row[10]),
            str(row[11]),
            str(row[12]),
        )

    @staticmethod
    def _select_sql() -> str:
        return """
            SELECT order_id, user_id, product_type, destination, rarity,
                   cost, summary, resolution, render_style, prompt_en,
                   status, created_at, updated_at
            FROM orders
        """

    @classmethod
    def _get_from_connection(
        cls,
        connection: sqlite3.Connection,
        order_id: str,
    ) -> tuple[OrderConfirmation, str, str, str] | None:
        row = connection.execute(
            cls._select_sql() + " WHERE order_id = ?",
            (str(order_id),),
        ).fetchone()
        return cls._from_row(row) if row is not None else None

    @staticmethod
    def _same_snapshot(
        left: OrderConfirmation,
        right: OrderConfirmation,
    ) -> bool:
        return left == right

    def get(self, order_id: str) -> OrderConfirmation | None:
        with self.db.transaction() as connection:
            result = self._get_from_connection(connection, order_id)
            return result[0] if result is not None else None

    def get_pending(self, user_id: str) -> OrderConfirmation | None:
        with self.db.transaction() as connection:
            row = connection.execute(
                self._select_sql()
                + """
                  WHERE user_id = ?
                    AND status = 'PENDING'
                  ORDER BY created_at DESC, rowid DESC
                  LIMIT 1
                  """,
                (str(user_id),),
            ).fetchone()
            return self._from_row(row)[0] if row is not None else None

    def get_latest_confirmed(self, user_id: str) -> OrderConfirmation | None:
        with self.db.transaction() as connection:
            row = connection.execute(
                self._select_sql()
                + """
                  WHERE user_id = ?
                    AND status = 'CONFIRMED'
                  ORDER BY created_at DESC, rowid DESC
                  LIMIT 1
                  """,
                (str(user_id),),
            ).fetchone()
            return self._from_row(row)[0] if row is not None else None

    def create_pending(self, order: OrderConfirmation) -> OrderConfirmation:
        if not ORDER_ID_PATTERN.fullmatch(order.order_id):
            raise ValueError("Formato de order_id inválido")
        if order.cost <= 0:
            raise ValueError("El coste del pedido debe ser positivo")
        with self.db.transaction(immediate=True) as connection:
            existing = self._get_from_connection(
                connection,
                order.order_id,
            )
            if existing is not None:
                existing_order, existing_status, _, _ = existing
                if not self._same_snapshot(existing_order, order):
                    raise EconomyPersistenceError(
                        f"Conflicto de identidad para pedido {order.order_id}"
                    )
                return existing_order

            pending = connection.execute(
                self._select_sql()
                + """
                  WHERE user_id = ?
                    AND status = 'PENDING'
                  ORDER BY created_at DESC, rowid DESC
                  LIMIT 1
                  """,
                (str(order.user_id),),
            ).fetchone()
            if pending is not None:
                existing_order = self._from_row(pending)[0]
                raise PendingOrderExistsError(existing_order)

            created_at = datetime.now(timezone.utc).isoformat()
            try:
                connection.execute(
                    """
                    INSERT INTO orders(
                        order_id, user_id, product_type, destination,
                        rarity, cost, summary, resolution, render_style,
                        prompt_en, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                    """,
                    (
                        order.order_id,
                        order.user_id,
                        order.product_type,
                        order.destination,
                        order.rarity,
                        int(order.cost),
                        order.summary,
                        order.resolution,
                        order.render_style,
                        order.prompt_en,
                        created_at,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise EconomyPersistenceError(
                    f"No se pudo persistir el pedido PENDING {order.order_id}"
                ) from error
            return order

    def confirm_order(
        self,
        order_id: str,
        user_id: str,
        *,
        wallet_store: CafeWalletStore,
    ) -> OrderConfirmResult:
        if wallet_store.path != self.db_path:
            raise EconomyPersistenceError(
                "Wallet y OrderStore no apuntan a la misma base SQLite"
            )

        with self.db.transaction(immediate=True) as connection:
            result = self._get_from_connection(connection, order_id)
            if result is None:
                raise ValueError(f"Pedido inexistente: {order_id}")

            order, status, _, _ = result
            if order.user_id != str(user_id):
                raise PermissionError("El pedido no pertenece al usuario que confirma")

            if status == "CONFIRMED":
                return OrderConfirmResult(
                    order,
                    "ALREADY_CONFIRMED",
                    False,
                )
            if status == "CANCELLED":
                return OrderConfirmResult(
                    order,
                    "CANCELLED",
                    False,
                )
            if status != "PENDING":
                raise EconomyPersistenceError(
                    f"Estado de pedido no soportado: {status}"
                )

            try:
                wallet_store.debit_in_transaction(
                    connection,
                    order.user_id,
                    order.cost,
                )
            except ValueError:
                return OrderConfirmResult(
                    order,
                    "INSUFFICIENT",
                    False,
                )

            cursor = connection.execute(
                """
                UPDATE orders
                SET status = 'CONFIRMED',
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?
                  AND status = 'PENDING'
                """,
                (order.order_id,),
            )
            if cursor.rowcount != 1:
                raise EconomyPersistenceError(
                    f"No se pudo confirmar el pedido {order.order_id}"
                )

            confirmed = self._get_from_connection(
                connection,
                order.order_id,
            )
            if confirmed is None or confirmed[1] != "CONFIRMED":
                raise EconomyPersistenceError(
                    f"No se pudo verificar la confirmación de {order.order_id}"
                )
            return OrderConfirmResult(
                confirmed[0],
                "CONFIRMED",
                True,
            )

    def cancel_order(
        self,
        order_id: str,
        user_id: str,
    ) -> OrderConfirmResult:
        with self.db.transaction(immediate=True) as connection:
            result = self._get_from_connection(connection, order_id)
            if result is None:
                raise ValueError(f"Pedido inexistente: {order_id}")

            order, status, _, _ = result
            if order.user_id != str(user_id):
                raise PermissionError("El pedido no pertenece al usuario que cancela")

            if status == "CANCELLED":
                return OrderConfirmResult(order, "CANCELLED", False)
            if status == "CONFIRMED":
                raise ValueError("Un pedido confirmado no puede cancelarse")
            if status != "PENDING":
                raise EconomyPersistenceError(
                    f"Estado de pedido no soportado: {status}"
                )

            cursor = connection.execute(
                """
                UPDATE orders
                SET status = 'CANCELLED',
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?
                  AND status = 'PENDING'
                """,
                (order.order_id,),
            )
            if cursor.rowcount != 1:
                raise EconomyPersistenceError(
                    f"No se pudo cancelar el pedido {order.order_id}"
                )
            cancelled = self._get_from_connection(
                connection,
                order.order_id,
            )
            if cancelled is None:
                raise EconomyPersistenceError(
                    f"No se pudo verificar la cancelación de {order.order_id}"
                )
            return OrderConfirmResult(
                cancelled[0],
                "CANCELLED",
                False,
            )

    def save(self, order: OrderConfirmation) -> None:
        """Compatibilidad estricta: nunca crea un pedido confirmado sin cargo."""
        current = self.get(order.order_id)
        if current is None:
            raise EconomyPersistenceError(
                "OrderStore.save() ya no puede crear pedidos directamente; "
                "usar create_pending() y confirm_order()"
            )
        if current != order:
            raise EconomyPersistenceError(
                f"El pedido {order.order_id} difiere del estado durable"
            )

    def migrate_legacy_json(self) -> int:
        """Importa orders.json explícitamente; no se ejecuta como write path normal."""
        if not self.legacy_path.is_file():
            return 0

        try:
            payload = json.loads(
                self.legacy_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EconomyPersistenceError(
                f"orders.json corrupto o ilegible: {self.legacy_path}"
            ) from error

        if not isinstance(payload, list):
            raise EconomyPersistenceError(
                "Formato heredado de orders.json inválido"
            )

        imported = 0
        migration_time = datetime.now(timezone.utc).isoformat()
        with self.db.transaction(immediate=True) as connection:
            for item in payload:
                if not isinstance(item, dict):
                    raise EconomyPersistenceError(
                        "Registro heredado de pedido inválido"
                    )
                try:
                    order = OrderConfirmation(
                        order_id=str(item["order_id"]),
                        user_id=str(item["user_id"]),
                        product_type=str(item["product_type"]),
                        destination=str(item["destination"]),
                        rarity=str(item["rarity"]),
                        cost=int(item["cost"]),
                        summary=str(item["summary"]),
                        resolution=str(item.get("resolution", "L")),
                        render_style=str(
                            item.get("render_style", "Classic Anime")
                        ),
                        prompt_en=str(item.get("prompt_en", "")),
                    )
                except (KeyError, TypeError, ValueError) as error:
                    raise EconomyPersistenceError(
                        "Registro heredado de pedido inválido"
                    ) from error

                if (
                    not ORDER_ID_PATTERN.fullmatch(order.order_id)
                    or order.cost <= 0
                ):
                    raise EconomyPersistenceError(
                        f"Identidad o coste heredado inválido para {order.order_id}"
                    )

                existing = self._get_from_connection(
                    connection,
                    order.order_id,
                )
                if existing is not None:
                    existing_order, status, _, _ = existing
                    if (
                        status == "CONFIRMED"
                        and self._same_snapshot(existing_order, order)
                    ):
                        continue
                    raise EconomyPersistenceError(
                        f"Conflicto de migración para pedido {order.order_id}"
                    )

                connection.execute(
                    """
                    INSERT INTO orders(
                        order_id, user_id, product_type, destination,
                        rarity, cost, summary, resolution, render_style,
                        prompt_en, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?)
                    """,
                    (
                        order.order_id,
                        order.user_id,
                        order.product_type,
                        order.destination,
                        order.rarity,
                        order.cost,
                        order.summary,
                        order.resolution,
                        order.render_style,
                        order.prompt_en,
                        migration_time,
                        migration_time,
                    ),
                )
                imported += 1
        return imported


class ComplaintStore:
    """Quejas y reembolsos en la misma DB que wallet/VIP, con resolución atómica."""

    LEGACY_FILENAME = "order_complaints.json"
    MIGRATION_KEY = "legacy:order_complaints:v1"

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root).expanduser().resolve() if root is not None else PROJECT_ROOT
        self.path = ECONOMY_DB_PATH if root is None else self.root / "config" / "bot_ia_economy.sqlite3"
        self.legacy_path = self.root / "config" / self.LEGACY_FILENAME
        self.db = EconomyDatabase(self.path)
        self._wallet_store = CafeWalletStore(self.root)
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
                items = payload.get("complaints", [])
                if not isinstance(items, list):
                    raise EconomyPersistenceError(
                        f"Listado de quejas heredado inválido: {self.legacy_path}"
                    )
                for item in items:
                    if not isinstance(item, dict):
                        raise EconomyPersistenceError(
                            "Registro heredado de queja inválido"
                        )
                    try:
                        complaint_id = str(item["complaint_id"])
                        user_id = str(item["user_id"])
                        chat_id = str(item["chat_id"])
                        text = str(item["text"])
                        order_id = str(item.get("order_id", ""))
                        product_type = str(item.get("product_type", ""))
                        points_paid = max(0, int(item.get("points_paid", 0)))
                        status = str(item.get("status", "OPEN"))
                        action = str(item.get("action", ""))
                        created_at = str(item.get("created_at", ""))
                        resolved_at = (
                            str(item["resolved_at"])
                            if item.get("resolved_at") is not None
                            else None
                        )
                        points_adjustment = int(
                            item.get("points_adjustment", 0)
                        )
                    except (KeyError, TypeError, ValueError) as error:
                        raise EconomyPersistenceError(
                            "Registro heredado de queja inválido"
                        ) from error

                    connection.execute(
                        """
                        INSERT OR IGNORE INTO complaints(
                            complaint_id, user_id, chat_id, text,
                            order_id, product_type, points_paid, status,
                            action, created_at, resolved_at, points_adjustment
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            complaint_id,
                            user_id,
                            chat_id,
                            text,
                            order_id,
                            product_type,
                            points_paid,
                            status,
                            action,
                            created_at,
                            resolved_at,
                            points_adjustment,
                        ),
                    )

            connection.execute(
                """
                INSERT OR REPLACE INTO schema_meta(key, value)
                VALUES (?, ?)
                """,
                (self.MIGRATION_KEY, "complete"),
            )

    @staticmethod
    def _from_row(row: tuple[object, ...]) -> ComplaintRecord:
        return ComplaintRecord(
            complaint_id=str(row[0]),
            user_id=str(row[1]),
            chat_id=str(row[2]),
            text=str(row[3]),
            order_id=str(row[4]),
            product_type=str(row[5]),
            points_paid=max(0, int(row[6])),
            status=str(row[7]),
            action=str(row[8]),
            created_at=str(row[9]),
        )

    def create(
        self,
        user_id: str,
        chat_id: str,
        text: str,
        *,
        order_id: str = "",
        product_type: str = "",
        points_paid: int = 0,
    ) -> ComplaintRecord:
        clean = " ".join(str(text).split()).strip()
        if not clean:
            raise ValueError("La queja no puede estar vacía.")
        if len(clean) > 4000:
            raise ValueError("La queja supera el límite de 4000 caracteres.")
        record = ComplaintRecord(
            complaint_id=secrets.token_hex(6),
            user_id=str(user_id),
            chat_id=str(chat_id),
            text=clean,
            order_id=str(order_id),
            product_type=str(product_type),
            points_paid=max(0, int(points_paid)),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO complaints(
                    complaint_id, user_id, chat_id, text,
                    order_id, product_type, points_paid, status,
                    action, created_at, resolved_at, points_adjustment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', '', ?, NULL, 0)
                """,
                (
                    record.complaint_id,
                    record.user_id,
                    record.chat_id,
                    record.text,
                    record.order_id,
                    record.product_type,
                    record.points_paid,
                    record.created_at,
                ),
            )
        return record

    def get(self, complaint_id: str) -> ComplaintRecord | None:
        with self.db.transaction() as connection:
            row = connection.execute(
                """
                SELECT complaint_id, user_id, chat_id, text,
                       order_id, product_type, points_paid, status,
                       action, created_at
                FROM complaints
                WHERE complaint_id = ?
                """,
                (str(complaint_id),),
            ).fetchone()
            return self._from_row(row) if row is not None else None

    def resolve(
        self,
        complaint_id: str,
        action: ComplaintAction,
        *,
        wallet_store: CafeWalletStore,
        registry: WaifuRegistry,
    ) -> ComplaintRecord:
        if action not in {"refund", "convert_image", "reject"}:
            raise ValueError("Acción administrativa inválida.")

        status_by_action = {
            "refund": "REFUNDED",
            "convert_image": "CONVERTED_TO_IMAGE",
            "reject": "REJECTED",
        }

        with self.db.transaction(immediate=True) as connection:
            row = connection.execute(
                """
                SELECT complaint_id, user_id, chat_id, text,
                       order_id, product_type, points_paid, status,
                       action, created_at
                FROM complaints
                WHERE complaint_id = ?
                """,
                (str(complaint_id),),
            ).fetchone()
            if row is None:
                raise ValueError(f"Reclamo inexistente: {complaint_id}")

            current = str(row[7])
            if current != "OPEN":
                raise ValueError(
                    f"El reclamo {complaint_id} ya fue resuelto ({current})."
                )

            user_id = str(row[1])
            points_paid = max(0, int(row[6]))
            adjustment = 0

            if action == "refund":
                order_id = str(row[4]).strip()
                if not order_id:
                    raise ValueError(
                        f"El reclamo {complaint_id} no referencia un pedido confirmado"
                    )

                order_row = connection.execute(
                    """
                    SELECT status, cost, user_id
                    FROM orders
                    WHERE order_id = ?
                    """,
                    (order_id,),
                ).fetchone()
                if order_row is None:
                    raise ValueError(
                        f"El pedido reclamado no existe: {order_id}"
                    )
                if str(order_row[2]) != user_id:
                    raise EconomyPersistenceError(
                        f"El pedido {order_id} no pertenece al usuario del reclamo"
                    )
                if str(order_row[0]) != "CONFIRMED":
                    raise ValueError(
                        f"El pedido {order_id} no está confirmado"
                    )
                order_cost = max(0, int(order_row[1]))
                if points_paid != order_cost:
                    raise EconomyPersistenceError(
                        f"Inconsistencia económica en pedido {order_id}: "
                        f"complaint={points_paid}, order={order_cost}"
                    )
                adjustment = order_cost

                if wallet_store.path != self.path:
                    raise EconomyPersistenceError(
                        "Wallet y ComplaintStore no apuntan a la misma base SQLite"
                    )
                wallet_store.credit_in_transaction(
                    connection,
                    user_id,
                    adjustment,
                )

            resolved_at = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                UPDATE complaints
                SET status = ?,
                    action = ?,
                    resolved_at = ?,
                    points_adjustment = ?
                WHERE complaint_id = ?
                  AND status = 'OPEN'
                """,
                (
                    status_by_action[action],
                    action,
                    resolved_at,
                    adjustment,
                    str(complaint_id),
                ),
            )

            resolved_row = connection.execute(
                """
                SELECT complaint_id, user_id, chat_id, text,
                       order_id, product_type, points_paid, status,
                       action, created_at
                FROM complaints
                WHERE complaint_id = ?
                """,
                (str(complaint_id),),
            ).fetchone()
            if resolved_row is None:
                raise EconomyPersistenceError(
                    f"No se pudo leer el reclamo recién resuelto: {complaint_id}"
                )
            result = self._from_row(resolved_row)

        # El registro visual de Waifu sigue fuera de la transacción económica.
        # Nunca se usa para decidir ni revertir el reembolso; un reintento no
        # duplica el crédito porque el estado OPEN ya quedó consumido.
        registry.record_complaint_balance(
            result.user_id,
            result.complaint_id,
            points_paid if action == "refund" else 0,
            result.status,
            balance_after=wallet_store.balance(result.user_id),
        )
        return result


def order_destination(product_type: str) -> str:
    normalized = str(product_type).strip().casefold()
    if normalized == "imagen ia personalizada":
        return "🖼️ Imagen IA Personalizada"
    return "🎴 Carta TCG para el Pool"


def new_order_id() -> str:
    return "ORD-" + secrets.token_hex(5).upper()
