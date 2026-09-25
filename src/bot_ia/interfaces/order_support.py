# -*- coding: utf-8 -*-
"""Confirmación de pedidos y gestión persistente de quejas/reembolsos."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
from typing import Literal

from bot_ia.paths import ECONOMY_DB_PATH, PROJECT_ROOT
from bot_ia.persistence.economy import EconomyDatabase, EconomyPersistenceError
from .cafe_economy import CafeWalletStore
from gui.waifu_registry import WaifuRegistry

ComplaintAction = Literal["refund", "convert_image", "reject"]


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


class OrderStore:
    """Registro persistente de pedidos confirmados; fuera del alcance SQLite de Fase 3."""

    def __init__(self, root: Path) -> None:
        self.path = Path(root) / "config" / "orders.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        import threading
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, object]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _save(self, items: list[dict[str, object]]) -> None:
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(items, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def save(self, order: OrderConfirmation) -> None:
        with self._lock:
            items = self._load()
            items = [
                item
                for item in items
                if str(item.get("order_id")) != order.order_id
            ]
            items.append(asdict(order))
            self._save(items)

    def get(self, order_id: str) -> OrderConfirmation | None:
        with self._lock:
            for item in self._load():
                if str(item.get("order_id")) == str(order_id):
                    return OrderConfirmation(
                        order_id=str(item.get("order_id", "")),
                        user_id=str(item.get("user_id", "")),
                        product_type=str(item.get("product_type", "")),
                        destination=str(item.get("destination", "")),
                        rarity=str(item.get("rarity", "")),
                        cost=max(0, int(item.get("cost", 0))),
                        summary=str(item.get("summary", "")),
                        resolution=str(item.get("resolution", "L")),
                        render_style=str(
                            item.get("render_style", "Classic Anime")
                        ),
                        prompt_en=str(item.get("prompt_en", "")),
                    )
        return None


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
            adjustment = points_paid if action == "refund" else 0

            if adjustment:
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
