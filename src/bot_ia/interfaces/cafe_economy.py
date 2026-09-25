# -*- coding: utf-8 -*-
"""Economía local del Café: puntos, precios, gacha y pity."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from random import SystemRandom
from typing import Callable


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


class CafeWalletStore:
    """Perfil local JSON: puntos y contadores de pity, sin red."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "config" / "cafe_wallets.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, int]]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        result: dict[str, dict[str, int]] = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                try:
                    result[str(key)] = {
                        "points": max(0, int(value.get("points", POINTS_STARTING_BALANCE))),
                        "pity_sr": max(0, int(value.get("pity_sr", 0))),
                        "pity_ur": max(0, int(value.get("pity_ur", 0))),
                    }
                except (TypeError, ValueError):
                    continue
            else:
                # Migración compatible con el formato anterior: user_id -> puntos.
                try:
                    result[str(key)] = {
                        "points": max(0, int(value)),
                        "pity_sr": 0,
                        "pity_ur": 0,
                    }
                except (TypeError, ValueError):
                    continue
        return result

    def _save(self, data: dict[str, dict[str, int]]) -> None:
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, user_id: str) -> CafeWallet:
        data = self._load()
        key = str(user_id)
        profile = data.get(key, {})
        return CafeWallet(
            key,
            profile.get("points", POINTS_STARTING_BALANCE),
            profile.get("pity_sr", 0),
            profile.get("pity_ur", 0),
        )

    def balance(self, user_id: str) -> int:
        return self.get(user_id).points

    def pity(self, user_id: str) -> tuple[int, int]:
        wallet = self.get(user_id)
        return wallet.pity_sr, wallet.pity_ur

    def _write_profile(self, user_id: str, profile: dict[str, int]) -> CafeWallet:
        data = self._load()
        key = str(user_id)
        data[key] = {
            "points": max(0, int(profile.get("points", POINTS_STARTING_BALANCE))),
            "pity_sr": max(0, int(profile.get("pity_sr", 0))),
            "pity_ur": max(0, int(profile.get("pity_ur", 0))),
        }
        self._save(data)
        return self.get(key)

    def credit(self, user_id: str, amount: int) -> CafeWallet:
        amount = max(0, int(amount))
        wallet = self.get(user_id)
        return self._write_profile(
            user_id,
            {
                "points": wallet.points + amount,
                "pity_sr": wallet.pity_sr,
                "pity_ur": wallet.pity_ur,
            },
        )

    def debit(self, user_id: str, amount: int) -> CafeWallet:
        amount = max(0, int(amount))
        wallet = self.get(user_id)
        if wallet.points < amount:
            raise ValueError("Puntos del Café insuficientes")
        return self._write_profile(
            user_id,
            {
                "points": wallet.points - amount,
                "pity_sr": wallet.pity_sr,
                "pity_ur": wallet.pity_ur,
            },
        )

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
        amount = GAME_REWARDS.get(str(game).casefold(), 0) * int(multiplier)
        return self.credit(user_id, amount)

    def boost_pity_sr(self, user_id: str, amount: int = 1) -> CafeWallet:
        """Aplica un pequeño avance de afinidad sin superar el umbral de garantía."""
        amount = max(0, int(amount))
        wallet = self.get(user_id)
        pity_sr = min(PITY_SR_LIMIT - 1, wallet.pity_sr + amount)
        return self._write_profile(
            user_id,
            {
                "points": wallet.points,
                "pity_sr": pity_sr,
                "pity_ur": wallet.pity_ur,
            },
        )

    def record_gacha(self, user_id: str, rarity: str) -> CafeWallet:
        wallet = self.get(user_id)
        pity_sr = 0 if rarity in {"SR", "UR"} else wallet.pity_sr
        pity_ur = 0 if rarity == "UR" else wallet.pity_ur
        return self._write_profile(
            user_id,
            {
                "points": wallet.points,
                "pity_sr": pity_sr,
                "pity_ur": pity_ur,
            },
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
    quote = quote_bebida_order(
        existing=existing,
        target_rarity=target_rarity,
        points=store.balance(user_id),
    )
    if not quote.can_afford:
        return quote
    store.debit(user_id, quote.cost)
    return quote


@dataclass(frozen=True, slots=True)
class GachaResult:
    rarity: str
    points_spent: int
    consolation: str
    pity_sr: int
    pity_ur: int
    affinity_bonus: bool = False


def draw_gacha(
    user_id: str,
    store: CafeWalletStore,
    *,
    roll: Callable[[], int] | None = None,
    maid: str = "Cami",
    affinity_level: int = 0,
) -> GachaResult:
    if store.balance(user_id) < GACHA_COST:
        raise ValueError("Puntos del Café insuficientes para el Gacha")

    wallet = store.get(user_id)
    next_sr = wallet.pity_sr + 1
    next_ur = wallet.pity_ur + 1

    if next_ur >= PITY_UR_LIMIT:
        rarity = "UR"
    elif next_sr >= PITY_SR_LIMIT:
        rarity = "SR"
    else:
        value = int((roll or (lambda: _RANDOM.randrange(100)))()) % 100
        if value < 70:
            rarity = "R"
        elif value < 95:
            rarity = "SR"
        else:
            rarity = "UR"

    store.debit(user_id, GACHA_COST)
    updated = store.record_gacha(user_id, rarity)
    affinity_bonus = rarity == "R" and int(affinity_level) >= 5
    if affinity_bonus:
        updated = store.boost_pity_sr(user_id, 1)
        consolation = (
            maid_consolation(maid, rarity)
            + " ❤️ Afinidad Lv.5+: ganas +1 progreso hacia la garantía SR."
        )
    else:
        consolation = maid_consolation(maid, rarity)
    return GachaResult(
        rarity,
        GACHA_COST,
        consolation,
        updated.pity_sr,
        updated.pity_ur,
        affinity_bonus,
    )


def maid_consolation(maid: str, rarity: str) -> str:
    name = maid.strip() or "Cami"
    if rarity == "R":
        if name.casefold() == "cari":
            return f"☕ {name}: ¡No te desanimes! Esta R es sólo el comienzo. Guarda tus puntos y vuelve a intentarlo."
        return f"☕ {name}: ¡Ánimo, maestro! Salió una R, pero tu próxima oportunidad puede traer algo especial."
    if rarity == "SR":
        return f"✨ {name}: ¡Buena tirada! Una SR ya es una pieza destacada de la colección."
    return f"🌟 {name}: ¡UR! Esta tirada fue excepcional. Guárdala en tu colección."


def pity_text(user_id: str, store: CafeWalletStore, maid: str = "Cami") -> str:
    wallet = store.get(user_id)
    name = maid.strip() or "Cami"
    return (
        f"☕ {name}: llevas {wallet.pity_sr}/{PITY_SR_LIMIT} tiradas hacia tu SR "
        f"y {wallet.pity_ur}/{PITY_UR_LIMIT} tiradas hacia tu UR.\n"
        "El contador SR se reinicia con SR/UR; el contador UR se reinicia con UR."
    )


def economy_price_text() -> str:
    return (
        "☕ PUNTOS DEL CAFÉ\n"
        f"• Bebida R / clonación R: {RARITY_PRICES['R']} puntos\n"
        f"• Bebida SR / clonación SR: {RARITY_PRICES['SR']} puntos\n"
        f"• Bebida UR / clonación UR: {RARITY_PRICES['UR']} puntos\n"
        f"• Bebida Especial (Custom Prompt): {RARITY_PRICES['SPECIAL']} puntos\n"
        f"• Gacha: {GACHA_COST} puntos\n"
        f"• Victoria 21: +{GAME_REWARDS['21']} puntos\n"
        f"• Victoria UNO: +{GAME_REWARDS['uno']} puntos\n"
        f"• Victoria PPT: +{GAME_REWARDS['ppt']} puntos"
    )
