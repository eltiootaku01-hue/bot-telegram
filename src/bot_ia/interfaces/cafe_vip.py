# -*- coding: utf-8 -*-
"""VIP opcional y economía pasiva: nunca bloquea el acceso SFW/Cantina."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal


VIP_ROLE = "Padrino del Café"
VIP_DISCORD_ROLE = "VIP"
VIP_ROOM_KEY = "zona_reservada"
DONATION_COMMAND = "/donar"
VIP_COMMAND = "/vip"
DONATION_BUTTON = "✨ Apoyar al Café"


@dataclass(frozen=True, slots=True)
class VipProfile:
    user_id: str
    vip: bool = False
    source: str = ""
    donated_stars: int = 0


class VipStore:
    """Registro local idempotente para concesiones manuales o donaciones voluntarias."""

    def __init__(self, root: Path) -> None:
        self.path = Path(root) / "config" / "cafe_vip.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, object]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _save(self, data: dict[str, dict[str, object]]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def get(self, user_id: str) -> VipProfile:
        item = self._load().get(str(user_id), {})
        return VipProfile(
            str(user_id),
            bool(item.get("vip", False)),
            str(item.get("source", "")),
            max(0, int(item.get("donated_stars", 0))),
        )

    def grant_manual(self, user_id: str) -> VipProfile:
        return self._grant(user_id, "manual", 0)

    def record_stars(self, user_id: str, stars: int) -> VipProfile:
        stars = max(0, int(stars))
        if stars <= 0:
            raise ValueError("La donación de Stars debe ser positiva")
        profile = self.get(user_id)
        return self._grant(user_id, "telegram_stars", profile.donated_stars + stars)

    def _grant(self, user_id: str, source: str, donated_stars: int) -> VipProfile:
        data = self._load()
        data[str(user_id)] = {
            "vip": True,
            "source": source,
            "donated_stars": donated_stars,
        }
        self._save(data)
        return self.get(user_id)

    def is_vip(self, user_id: str) -> bool:
        return self.get(user_id).vip


def vip_policy_text() -> str:
    return (
        "✨ VIP / Padrino del Café es opcional.\n"
        "El acceso a SFW y #cantina-18 sigue siendo 100% gratuito.\n"
        "VIP sólo añade beneficios cosméticos y acceso opcional a #zona-reservada."
    )


def donation_keyboard() -> tuple[tuple[tuple[str, str], ...], ...]:
    return (((DONATION_BUTTON, "vip:donate"),),)


def vip_status_text(user_id: str, store: VipStore) -> str:
    profile = store.get(user_id)
    if profile.vip:
        return (
            "✨ Estado VIP: activo.\n"
            "Beneficio: #zona-reservada y distintivo cosmético.\n"
            f"Origen: {profile.source or 'manual'}."
        )
    return vip_policy_text() + "\n\nEstado: no VIP. Si quieres apoyar, usa /donar."


def validate_donation_event(user_id: str, payload: dict[str, object]) -> VipProfile:
    """Valida un evento ya confirmado por Telegram; no convierte texto del usuario en pago."""
    if str(payload.get("currency", "")).upper() != "XTR":
        raise ValueError("La donación de Telegram Stars debe usar XTR")
    amount = int(payload.get("total_amount", 0))
    if amount <= 0:
        raise ValueError("Pago Stars inválido")
    return VipStore(Path.cwd()).record_stars(user_id, amount)


def discord_vip_permission_overwrite(role_id: str) -> dict[str, object]:
    # Ver canal + leer historial + adjuntar archivos; no altera los canales públicos.
    return {
        "id": str(role_id),
        "type": 0,
        "allow": str((1 << 10) | (1 << 15)),
    }
