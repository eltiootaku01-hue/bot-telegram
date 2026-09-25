from __future__ import annotations
import re, unicodedata
from .models import ConversationIntent, ParseResult

def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))

class DeterministicParser:
    _patterns = (
        (ConversationIntent.GREETING, re.compile(r"\b(?:hola|holi|buenas|hello|hey|buenos\s+dias|buenas\s+(?:tardes|noches))\b")),
        (ConversationIntent.STATUS_QUERY, re.compile(r"\b(?:como\s+estas|como\s+esta|estado|status|que\s+tal|estas\s+bien)\b")),
        (ConversationIntent.GAME_INVITE, re.compile(r"\b(?:poker|jugar|jugamos|partida|desafio|challenge|reto|invito)\b")),
        (ConversationIntent.GACHA_ROLL, re.compile(r"\b(?:roll|tirada|tirar|gacha|sacar\s+(?:carta|cartas))\b")),
        (ConversationIntent.CLAIM_CARD, re.compile(r"\b(?:claim|reclamar|reclama|reclamo)\b")),
        (ConversationIntent.VIEW_RATES, re.compile(r"\b(?:rates|probabilidades|tasas|chances)\b")),
        (ConversationIntent.INVENTORY_SEARCH, re.compile(r"\b(?:inventario|mis\s+cartas|mis\s+cards)\b")),
        (ConversationIntent.CATALOG_QUERY, re.compile(r"\b(?:catalogo|catálogo|catalog|coleccion|colección)\b")),
        (ConversationIntent.MINI_APP_OPEN, re.compile(r"\b(?:mini\s*app|miniapp|aplicacion|aplicación|abrir\s+app)\b")),
        (ConversationIntent.CAMPANA_FULL, re.compile(r"\b(?:campana|campanita|tocar\s+la\s+campana)\b")),
        (ConversationIntent.SECURITY_STATUS, re.compile(r"\b(?:seguridad|security|bloqueo|lockout|estado\s+de\s+seguridad)\b")),
        (ConversationIntent.HELP_SYSTEM, re.compile(r"\b(?:ayuda|help|comandos|help\s+system)\b")),
    )
    def parse(self, text: str | None) -> ParseResult:
        normalized = _normalize(text or "").strip()
        for intent, pattern in self._patterns:
            match = pattern.search(normalized)
            if match: return ParseResult(intent, match.group(0))
        return ParseResult(ConversationIntent.UNKNOWN)
