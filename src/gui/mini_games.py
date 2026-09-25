# -*- coding: utf-8 -*-
"""Mini-juegos locales deterministas y sin WebQueue para la Taberna."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import SystemRandom
import re


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
class BlackjackState:
    player_cards: list[str] = field(default_factory=list)
    dealer_cards: list[str] = field(default_factory=list)
    finished: bool = False


class LocalGameRouter:
    """Router de juegos sin red; mantiene estado aislado por usuario y mesera."""

    def __init__(self) -> None:
        self._blackjack: dict[tuple[str, str], BlackjackState] = {}

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

    def _ppt_response(self, message: str) -> str | None:
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
        return f"PPT local · tú: {choice} · mesera: {bot} · {result}."

    def route(self, message: str, user_id: str, bot_id: str) -> str | None:
        normalized = " ".join(message.casefold().strip().split())
        ppt = self._ppt_response(normalized)
        if ppt is not None:
            return ppt
        if any(token in normalized for token in ("21", "blackjack", "black jack")):
            action = normalized
            for prefix in ("21", "blackjack", "black jack"):
                action = action.replace(prefix, " ")
            action = " ".join(action.split())
            return self._blackjack_response(user_id, bot_id, action or "nuevo")
        if any(token in normalized for token in ("piedra", "papel", "tijera")):
            return self._ppt_response(normalized)
        if any(token in normalized for token in ("uno", "juego de cartas")):
            return (
                "UNO local · catálogo disponible. Para jugar una partida completa "
                "todavía se usa el registro de cartas; no se abrió WebQueue."
            )
        return None
