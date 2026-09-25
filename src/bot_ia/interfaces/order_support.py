# -*- coding: utf-8 -*-
"""Confirmación de pedidos y gestión persistente de quejas/reembolsos."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import threading
from typing import Literal

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


class ComplaintStore:
    """Persistencia atómica y anti-doble-resolución para reclamos."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / "config" / "order_complaints.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _load(self) -> dict[str, object]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _save(self, payload: dict[str, object]) -> None:
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

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
        with self._lock:
            payload = self._load()
            items = payload.setdefault("complaints", [])
            if not isinstance(items, list):
                items = []
                payload["complaints"] = items
            items.append(asdict(record))
            self._save(payload)
        return record

    def get(self, complaint_id: str) -> ComplaintRecord | None:
        with self._lock:
            payload = self._load()
            items = payload.get("complaints", [])
            if not isinstance(items, list):
                return None
            for item in items:
                if isinstance(item, dict) and str(item.get("complaint_id")) == str(complaint_id):
                    return ComplaintRecord(
                        complaint_id=str(item.get("complaint_id", "")),
                        user_id=str(item.get("user_id", "")),
                        chat_id=str(item.get("chat_id", "")),
                        text=str(item.get("text", "")),
                        order_id=str(item.get("order_id", "")),
                        product_type=str(item.get("product_type", "")),
                        points_paid=max(0, int(item.get("points_paid", 0))),
                        status=str(item.get("status", "OPEN")),
                        action=str(item.get("action", "")),
                        created_at=str(item.get("created_at", "")),
                    )
        return None

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
        with self._lock:
            payload = self._load()
            items = payload.get("complaints", [])
            if not isinstance(items, list):
                raise ValueError("Registro de quejas inválido.")
            for item in items:
                if not isinstance(item, dict) or str(item.get("complaint_id")) != str(complaint_id):
                    continue
                current = str(item.get("status", "OPEN"))
                if current != "OPEN":
                    raise ValueError(f"El reclamo {complaint_id} ya fue resuelto ({current}).")
                user_id = str(item.get("user_id", ""))
                points_paid = max(0, int(item.get("points_paid", 0)))
                if action == "refund" and points_paid:
                    wallet_store.credit(user_id, points_paid)
                item["status"] = {
                    "refund": "REFUNDED",
                    "convert_image": "CONVERTED_TO_IMAGE",
                    "reject": "REJECTED",
                }[action]
                item["action"] = action
                item["resolved_at"] = datetime.now(timezone.utc).isoformat()
                item["points_adjustment"] = points_paid if action == "refund" else 0
                # waifu_registry.json conserva el snapshot/ledger administrativo.
                registry.record_complaint_balance(
                    user_id,
                    complaint_id,
                    points_paid if action == "refund" else 0,
                    item["status"],
                    balance_after=wallet_store.balance(user_id),
                )
                self._save(payload)
                return self.get(complaint_id)  # type: ignore[return-value]
        raise ValueError(f"Reclamo inexistente: {complaint_id}")


def order_destination(product_type: str) -> str:
    normalized = str(product_type).strip().casefold()
    if normalized == "imagen ia personalizada":
        return "🖼️ Imagen IA Personalizada"
    return "🎴 Carta TCG para el Pool"


def new_order_id() -> str:
    return "ORD-" + secrets.token_hex(5).upper()
