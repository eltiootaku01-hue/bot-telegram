# -*- coding: utf-8 -*-
"""Economía local del Café: puntos, precios, gacha y diálogos de consuelo."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from random import SystemRandom
from typing import Callable


POINTS_STARTING_BALANCE = 50
ORDER_COST_NORMAL = 10
ORDER_COST_HIGH = 25
GACHA_COST = 10
GAME_REWARDS = {"21": 10, "uno": 12, "ppt": 5}
RARITY_WEIGHTS = (("R", 70), ("SR", 25), ("UR", 5))

_RANDOM = SystemRandom()


@dataclass(frozen=True, slots=True)
class CafeWallet:
    user_id: str
    points: int = POINTS_STARTING_BALANCE


class CafeWalletStore:
    """Monedero JSON local, atómico y sin red."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "config" / "cafe_wallets.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, int]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        result: dict[str, int] = {}
        for key, value in payload.items():
            try:
                result[str(key)] = max(0, int(value))
            except (TypeError, ValueError):
                continue
        return result

    def _save(self, data: dict[str, int]) -> None:
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, user_id: str) -> CafeWallet:
        data = self._load()
        key = str(user_id)
        return CafeWallet(key, data.get(key, POINTS_STARTING_BALANCE))

    def balance(self, user_id: str) -> int:
        return self.get(user_id).points

    def credit(self, user_id: str, amount: int) -> CafeWallet:
        amount = max(0, int(amount))
        data = self._load()
        key = str(user_id)
        data[key] = data.get(key, POINTS_STARTING_BALANCE) + amount
        self._save(data)
        return CafeWallet(key, data[key])

    def debit(self, user_id: str, amount: int) -> CafeWallet:
        amount = max(0, int(amount))
        data = self._load()
        key = str(user_id)
        current = data.get(key, POINTS_STARTING_BALANCE)
        if current < amount:
            raise ValueError("Puntos del Café insuficientes")
        data[key] = current - amount
        self._save(data)
        return CafeWallet(key, data[key])

    def reward_game(self, user_id: str, game: str, *, won: bool) -> CafeWallet:
        if not won:
            return self.get(user_id)
        amount = GAME_REWARDS.get(str(game).casefold(), 0)
        return self.credit(user_id, amount)


@dataclass(frozen=True, slots=True)
class OrderQuote:
    cost: int
    kind: str
    can_afford: bool


def quote_bebida_order(*, existing: bool, points: int) -> OrderQuote:
    cost = ORDER_COST_NORMAL if existing else ORDER_COST_HIGH
    return OrderQuote(cost, "clonación" if existing else "personalizada", points >= cost)


def purchase_bebida_order(store: CafeWalletStore, user_id: str, *, existing: bool) -> OrderQuote:
    quote = quote_bebida_order(existing=existing, points=store.balance(user_id))
    if not quote.can_afford:
        return quote
    store.debit(user_id, quote.cost)
    return quote


@dataclass(frozen=True, slots=True)
class GachaResult:
    rarity: str
    points_spent: int
    consolation: str


def draw_gacha(
    user_id: str,
    store: CafeWalletStore,
    *,
    roll: Callable[[], int] | None = None,
    maid: str = "Cami",
) -> GachaResult:
    if store.balance(user_id) < GACHA_COST:
        raise ValueError("Puntos del Café insuficientes para el Gacha")
    store.debit(user_id, GACHA_COST)
    value = int((roll or (lambda: _RANDOM.randrange(100)))())
    value %= 100
    if value < 70:
        rarity = "R"
    elif value < 95:
        rarity = "SR"
    else:
        rarity = "UR"
    consolation = maid_consolation(maid, rarity)
    return GachaResult(rarity, GACHA_COST, consolation)


def maid_consolation(maid: str, rarity: str) -> str:
    name = maid.strip() or "Cami"
    if rarity == "R":
        if name.casefold() == "cari":
            return f"☕ {name}: ¡No te desanimes! Esta R es sólo el comienzo. Guarda tus puntos y vuelve a intentarlo."
        return f"☕ {name}: ¡Ánimo, maestro! Salió una R, pero tu próxima oportunidad puede traer algo especial."
    if rarity == "SR":
        return f"✨ {name}: ¡Buena tirada! Una SR ya es una pieza destacada de la colección."
    return f"🌟 {name}: ¡UR! Esta tirada fue excepcional. Guárdala en tu colección."


def economy_price_text() -> str:
    return (
        "☕ PUNTOS DEL CAFÉ\n"
        f"• Clonar carta existente: {ORDER_COST_NORMAL} puntos\n"
        f"• Carta personalizada: {ORDER_COST_HIGH} puntos\n"
        f"• Gacha: {GACHA_COST} puntos\n"
        f"• Victoria 21: +{GAME_REWARDS['21']} puntos\n"
        f"• Victoria UNO: +{GAME_REWARDS['uno']} puntos\n"
        f"• Victoria PPT: +{GAME_REWARDS['ppt']} puntos"
    )
