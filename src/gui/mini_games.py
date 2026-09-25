# -*- coding: utf-8 -*-
"""Mini-juegos locales deterministas y sin WebQueue para la Taberna."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import SystemRandom
import re

from bot_ia.interfaces.cafe_economy import CafeWalletStore


_RANDOM = SystemRandom()
PPT_CHOICES = ("piedra", "papel", "tijera")
PPT_ALIASES = {
    "p": "piedra",
    "piedra": "piedra",
    "r": "piedra",
    "papel": "papel",
    "a": "papel",
    "tijera": "tijera",
    "t": "tijera",
}
BLACKJACK_ACTIONS = {"carta", "hit", "pedir", "otra", "plantarse", "plantar", "stand", "paso"}
GAME_HOSTS = {"ppt": "Cari", "21": "Sunna", "uno": "Cami", "mesa": "Chie"}
UNO_COLORS = ("rojo", "amarillo", "verde", "azul")
UNO_VALUES = tuple("0 1 2 3 4 5 6 7 8 9 +2 salto reversa".split())

CARD_VALUES = {
    "A": 11,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
}


@dataclass(slots=True)
class UnoState:
    player_cards: list[str] = field(default_factory=list)
    host_cards: list[str] = field(default_factory=list)
    top_card: str = ""
    finished: bool = False


@dataclass(slots=True)
class BlackjackState:
    player_cards: list[str] = field(default_factory=list)
    dealer_cards: list[str] = field(default_factory=list)
    finished: bool = False


class LocalGameRouter:
    """Router de juegos sin red; mantiene estado aislado por usuario y mesera."""

    def __init__(self, wallet_store: CafeWalletStore | None = None) -> None:
        self._wallet_store = wallet_store
        self._blackjack: dict[tuple[str, str], BlackjackState] = {}
        self._uno: dict[tuple[str, str], UnoState] = {}

    @staticmethod
    def _key(user_id: str, bot_id: str) -> tuple[str, str]:
        return str(user_id), str(bot_id)

    @staticmethod
    def _deck() -> list[str]:
        return [rank for rank in CARD_VALUES for _ in range(4)]

    @staticmethod
    def _score(cards: list[str]) -> int:
        total = sum(CARD_VALUES[card] for card in cards)
        aces = cards.count("A")
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    @classmethod
    def _new_blackjack(cls) -> BlackjackState:
        deck = cls._deck()
        _RANDOM.shuffle(deck)
        state = BlackjackState(
            player_cards=[deck.pop(), deck.pop()],
            dealer_cards=[deck.pop(), deck.pop()],
        )
        return state

    def _blackjack_response(
        self,
        user_id: str,
        bot_id: str,
        action: str,
    ) -> str:
        key = self._key(user_id, bot_id)
        action = action.casefold()
        state = self._blackjack.get(key)
        if state is None or action in {"nuevo", "21", "blackjack", "reiniciar"}:
            state = self._new_blackjack()
            self._blackjack[key] = state
            action = "estado"

        if state.finished:
            return (
                "La partida de 21 ya terminó. Escribe «21 nuevo» para otra "
                "mano local."
            )

        deck = self._deck()
        if action in {"carta", "hit", "pedir", "otra"}:
            state.player_cards.append(_RANDOM.choice(deck))
            player = self._score(state.player_cards)
            if player > 21:
                state.finished = True
                return (
                    f"21 local · tus cartas: {', '.join(state.player_cards)} "
                    f"({player}). Te pasaste. Escribe «21 nuevo» para reiniciar."
                )
            if player == 21:
                return self._finish_blackjack(state, natural=True)
            return (
                f"21 local · tus cartas: {', '.join(state.player_cards)} "
                f"({player}). Dealer visible: {state.dealer_cards[0]}. "
                "Escribe «carta» o «plantarse»."
            )

        if action in {"plantarse", "plantar", "stand", "paso", "estado"}:
            return self._finish_blackjack(state, natural=False)

        return (
            "21 local: usa «21 nuevo», «carta» o «plantarse». "
            "No se usa WebQueue."
        )

    @staticmethod
    def _new_uno() -> UnoState:
        deck = [f"{color} {value}" for color in UNO_COLORS for value in UNO_VALUES]
        _RANDOM.shuffle(deck)
        return UnoState(
            player_cards=[deck.pop() for _ in range(5)],
            host_cards=[deck.pop() for _ in range(5)],
            top_card=deck.pop(),
        )

    def _uno_response(self, user_id: str, bot_id: str, action: str) -> str:
        key = self._key(user_id, bot_id)
        action = action.casefold().strip()
        state = self._uno.get(key)
        if state is None or action in {"nuevo", "reiniciar"}:
            state = self._new_uno()
            self._uno[key] = state
            return (
                f"UNO local · anfitriona: {GAME_HOSTS['uno']} · "
                f"carta en mesa: {state.top_card} · "
                f"tus cartas: {', '.join(state.player_cards)}. "
                "Escribe «robar» o «UNO jugar»."
            )
        if state.finished:
            return "La partida de UNO ya terminó. Escribe «UNO nuevo» para reiniciar."
        if action in {"robar", "carta", "pedir"}:
            color, value = state.top_card.split(" ", 1)
            candidates = [
                card for card in state.player_cards
                if card.startswith(color + " ") or card.endswith(" " + value)
            ]
            if not candidates:
                new_card = f"{_RANDOM.choice(UNO_COLORS)} {_RANDOM.choice(UNO_VALUES)}"
                state.player_cards.append(new_card)
                return (
                    f"UNO local · robaste {new_card}. "
                    f"Anfitriona: {GAME_HOSTS['uno']}."
                )
            state.top_card = candidates[0]
            state.player_cards.remove(candidates[0])
            if not state.player_cards:
                state.finished = True
                return f"UNO local · ¡ganaste! Anfitriona: {GAME_HOSTS['uno']}."
            return (
                f"UNO local · jugaste {state.top_card}. "
                f"Te quedan {len(state.player_cards)} cartas. "
                f"Anfitriona: {GAME_HOSTS['uno']}."
            )
        return (
            f"UNO local · anfitriona: {GAME_HOSTS['uno']} · "
            "usa «UNO nuevo», «robar» o «UNO jugar»."
        )

    def _finish_blackjack(self, state: BlackjackState, *, natural: bool) -> str:
        player = self._score(state.player_cards)
        while self._score(state.dealer_cards) < 17:
            state.dealer_cards.append(_RANDOM.choice(self._deck()))
        dealer = self._score(state.dealer_cards)
        state.finished = True
        if player > 21:
            result = "perdiste"
        elif dealer > 21 or player > dealer:
            result = "ganaste"
        elif player == dealer:
            result = "empate"
        else:
            result = "perdiste"
        prefix = "¡21!" if natural or player == 21 else "21 local"
        return (
            f"{prefix} · tú: {player} [{', '.join(state.player_cards)}] · "
            f"dealer: {dealer} [{', '.join(state.dealer_cards)}] · {result}. "
            "Escribe «21 nuevo» para otra mano."
        )

    @staticmethod
    def _parse_ppt(message: str) -> str | None:
        tokens = re.findall(r"[a-záéíóúñ]+", message.casefold())
        for token in tokens:
            normalized = (
                token.replace("á", "a").replace("é", "e")
                .replace("í", "i").replace("ó", "o")
                .replace("ú", "u").replace("ñ", "n")
            )
            if normalized in PPT_ALIASES:
                return PPT_ALIASES[normalized]
        return None

    def _ppt_response(self, message: str, user_id: str = "anonymous") -> str | None:
        choice = self._parse_ppt(message)
        if choice is None:
            return None
        bot = _RANDOM.choice(PPT_CHOICES)
        if choice == bot:
            result = "empate"
        elif (choice, bot) in {
            ("piedra", "tijera"),
            ("papel", "piedra"),
            ("tijera", "papel"),
        }:
            result = "ganaste"
        else:
            result = "perdiste"
        if result == "ganaste" and self._wallet_store is not None:
            self._wallet_store.reward_game(user_id, "ppt", won=True)
        return f"PPT local · anfitriona: {GAME_HOSTS['ppt']} · tú: {choice} · mesera: {bot} · {result}."

    def route(self, message: str, user_id: str, bot_id: str) -> str | None:
        normalized = " ".join(message.casefold().strip().split())
        ppt = self._ppt_response(normalized, user_id)
        if ppt is not None:
            return ppt
        if any(token in normalized for token in ("21", "blackjack", "black jack")):
            action = normalized
            for prefix in ("21", "blackjack", "black jack"):
                action = action.replace(prefix, " ")
            action = " ".join(action.split())
            return self._blackjack_response(user_id, bot_id, action or "nuevo")
        if any(token in normalized for token in ("piedra", "papel", "tijera")):
            return self._ppt_response(normalized, user_id)
        if any(token in normalized for token in ("uno", "juego de cartas")):
            action = normalized.replace("uno", " ").strip() or "nuevo"
            return self._uno_response(user_id, bot_id, action)
        if any(token in normalized for token in ("juego de mesa", "mesa local")):
            return (
                f"Mesa local · anfitriona: {GAME_HOSTS['mesa']} · "
                "catálogo disponible: UNO, 21 y PPT. "
                "Todo se resuelve localmente; WebQueue omitido."
            )
        return None
