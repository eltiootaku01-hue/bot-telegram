# -*- coding: utf-8 -*-
"""VIP opcional y economía pasiva sobre la base SQLite compartida."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from bot_ia.paths import ECONOMY_DB_PATH, PROJECT_ROOT
from bot_ia.persistence.economy import EconomyDatabase, EconomyPersistenceError


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
    """Registro VIP compartido entre procesos mediante SQLite WAL."""

    LEGACY_FILENAME = "cafe_vip.json"
    MIGRATION_KEY = "legacy:cafe_vip:v1"

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
                    if not isinstance(value, dict):
                        raise EconomyPersistenceError(
                            f"Registro VIP heredado inválido para {user_id!r}"
                        )
                    try:
                        vip = 1 if bool(value.get("vip", False)) else 0
                        source = str(value.get("source", ""))
                        donated_stars = max(
                            0,
                            int(value.get("donated_stars", 0)),
                        )
                    except (TypeError, ValueError) as error:
                        raise EconomyPersistenceError(
                            f"Registro VIP heredado inválido para {user_id!r}"
                        ) from error
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO vip(
                            user_id, vip, source, donated_stars
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(user_id),
                            vip,
                            source,
                            donated_stars,
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
    def _from_row(user_id: str, row: tuple[object, ...] | None) -> VipProfile:
        if row is None:
            return VipProfile(str(user_id))
        return VipProfile(
            str(user_id),
            bool(int(row[0])),
            str(row[1]),
            max(0, int(row[2])),
        )

    def get(self, user_id: str) -> VipProfile:
        with self.db.transaction() as connection:
            row = connection.execute(
                """
                SELECT vip, source, donated_stars
                FROM vip
                WHERE user_id = ?
                """,
                (str(user_id),),
            ).fetchone()
            return self._from_row(str(user_id), row)

    def grant_manual(self, user_id: str) -> VipProfile:
        with self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO vip(user_id, vip, source, donated_stars)
                VALUES (?, 1, 'manual', 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    vip = 1,
                    source = 'manual',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(user_id),),
            )
            row = connection.execute(
                """
                SELECT vip, source, donated_stars
                FROM vip WHERE user_id = ?
                """,
                (str(user_id),),
            ).fetchone()
            return self._from_row(str(user_id), row)

    def record_stars(self, user_id: str, stars: int) -> VipProfile:
        stars = max(0, int(stars))
        if stars <= 0:
            raise ValueError("La donación de Stars debe ser positiva")
        with self.db.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO vip(
                    user_id, vip, source, donated_stars
                ) VALUES (?, 1, 'telegram_stars', ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    vip = 1,
                    source = 'telegram_stars',
                    donated_stars = vip.donated_stars + excluded.donated_stars,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(user_id), stars),
            )
            row = connection.execute(
                """
                SELECT vip, source, donated_stars
                FROM vip WHERE user_id = ?
                """,
                (str(user_id),),
            ).fetchone()
            return self._from_row(str(user_id), row)

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


def validate_donation_event(
    user_id: str,
    payload: dict[str, object],
) -> VipProfile:
    """Valida un evento ya confirmado por Telegram y escribe en la DB única."""
    if str(payload.get("currency", "")).upper() != "XTR":
        raise ValueError("La donación de Telegram Stars debe usar XTR")
    amount = int(payload.get("total_amount", 0))
    if amount <= 0:
        raise ValueError("Pago Stars inválido")
    return VipStore(PROJECT_ROOT).record_stars(
        user_id,
        amount,
    )


def discord_vip_permission_overwrite(
    role_id: str,
) -> dict[str, object]:
    # Ver canal + leer historial + adjuntar archivos; no altera los canales públicos.
    return {
        "id": str(role_id),
        "type": 0,
        "allow": str((1 << 10) | (1 << 15)),
    }
