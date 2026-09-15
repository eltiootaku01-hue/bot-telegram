from __future__ import annotations

from dataclasses import dataclass

from app.characters.director import CharacterDirector, CharacterResponse
from app.characters.models import CharacterIntent
from app.core.identity import BotIdentity


@dataclass(frozen=True, slots=True)
class RoutineWindow:
    """Authored time window that maps an identity to a conversational intent."""

    key: str
    identity: BotIdentity
    label: str
    start_hour: int
    end_hour: int
    intent: CharacterIntent
    weekdays: frozenset[int] = frozenset(range(7))

    def __post_init__(self) -> None:
        if not 0 <= self.start_hour <= 23:
            raise ValueError("Routine start_hour must be between 0 and 23")
        if not 0 <= self.end_hour <= 24:
            raise ValueError("Routine end_hour must be between 0 and 24")
        if self.start_hour == self.end_hour:
            raise ValueError("Routine window cannot have zero duration")
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("Routine weekdays must use datetime weekday values 0..6")

    def matches(self, weekday: int, hour: int) -> bool:
        """Return whether this window is active at the supplied whole hour."""
        if weekday not in self.weekdays:
            return False
        if self.start_hour < self.end_hour:
            return self.start_hour <= hour < self.end_hour
        return hour >= self.start_hour or hour < self.end_hour


ROUTINE_WINDOWS: tuple[RoutineWindow, ...] = (
    RoutineWindow(
        "cari-opening",
        BotIdentity.CARI,
        "apertura del Café Otaku",
        8,
        11,
        CharacterIntent.GREETING,
    ),
    RoutineWindow(
        "cari-service",
        BotIdentity.CARI,
        "atención del café",
        11,
        16,
        CharacterIntent.BUSY,
    ),
    RoutineWindow(
        "cari-afternoon",
        BotIdentity.CARI,
        "tarde de anime y manga",
        16,
        19,
        CharacterIntent.HELP,
    ),
    RoutineWindow(
        "cari-closing",
        BotIdentity.CARI,
        "cierre tranquilo",
        19,
        24,
        CharacterIntent.QUIET,
    ),
    RoutineWindow(
        "sunna-night-game",
        BotIdentity.SUNNA,
        "sesión nocturna de juego",
        18,
        24,
        CharacterIntent.BUSY,
    ),
    RoutineWindow(
        "sunna-rest",
        BotIdentity.SUNNA,
        "pausa y descanso",
        0,
        18,
        CharacterIntent.QUIET,
    ),
    RoutineWindow(
        "cami-morning-archive",
        BotIdentity.CAMI,
        "archivo de la mañana",
        9,
        13,
        CharacterIntent.BUSY,
    ),
    RoutineWindow(
        "cami-afternoon-checks",
        BotIdentity.CAMI,
        "revisión de la tarde",
        13,
        19,
        CharacterIntent.BUSY,
    ),
    RoutineWindow(
        "cami-night-closeout",
        BotIdentity.CAMI,
        "cierre del archivo",
        19,
        23,
        CharacterIntent.QUIET,
    ),
    RoutineWindow(
        "chie-morning-notices",
        BotIdentity.CHIE,
        "avisos de la mañana",
        8,
        12,
        CharacterIntent.BUSY,
    ),
    RoutineWindow(
        "chie-afternoon-coordination",
        BotIdentity.CHIE,
        "coordinación de la tarde",
        12,
        20,
        CharacterIntent.BUSY,
    ),
    RoutineWindow(
        "chie-night-quiet",
        BotIdentity.CHIE,
        "cierre de coordinación",
        20,
        24,
        CharacterIntent.QUIET,
    ),
)


class RoutineDirector:
    """Deterministically selects authored character speech for a routine window."""

    def __init__(
        self,
        windows: tuple[RoutineWindow, ...] = ROUTINE_WINDOWS,
        director: CharacterDirector | None = None,
    ) -> None:
        self._windows = windows
        self._director = director or CharacterDirector()

    def windows_for(self, identity: BotIdentity, weekday: int, hour: int) -> tuple[RoutineWindow, ...]:
        if not 0 <= weekday <= 6:
            raise ValueError("weekday must be between 0 and 6")
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        return tuple(
            window
            for window in self._windows
            if window.identity is identity and window.matches(weekday, hour)
        )

    def choose(
        self,
        identity: BotIdentity,
        weekday: int,
        hour: int,
        *,
        roll: int = 0,
    ) -> tuple[RoutineWindow, CharacterResponse] | None:
        windows = self.windows_for(identity, weekday, hour)
        if not windows:
            return None
        window = windows[abs(weekday * 24 + hour + roll) % len(windows)]
        response = self._director.choose(identity, window.intent, roll=roll)
        if response is None:
            return None
        return window, response
