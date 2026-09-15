import pytest

from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent
from app.characters.routines import ROUTINE_WINDOWS, RoutineDirector, RoutineWindow
from app.core.identity import BotIdentity


def test_routine_catalog_covers_all_identities() -> None:
    assert {window.identity for window in ROUTINE_WINDOWS} == set(BotIdentity)


def test_every_routine_intent_has_authored_scene() -> None:
    director = CharacterDirector()

    for window in ROUTINE_WINDOWS:
        assert director.choose(window.identity, window.intent, roll=0) is not None, window.key


def test_routine_window_matches_regular_and_overnight_ranges() -> None:
    daytime = RoutineWindow(
        "day",
        BotIdentity.CARI,
        "daytime",
        8,
        12,
        CharacterIntent.BUSY,
    )
    overnight = RoutineWindow(
        "night",
        BotIdentity.SUNNA,
        "night",
        22,
        6,
        CharacterIntent.QUIET,
    )

    assert daytime.matches(0, 8)
    assert daytime.matches(0, 11)
    assert not daytime.matches(0, 12)
    assert overnight.matches(0, 23)
    assert overnight.matches(1, 2)
    assert not overnight.matches(1, 12)


def test_routine_director_returns_authored_scene_for_active_window() -> None:
    director = RoutineDirector()

    chosen = director.choose(BotIdentity.CARI, weekday=0, hour=10, roll=0)

    assert chosen is not None
    window, response = chosen
    assert window.intent is CharacterIntent.GREETING
    assert response.scene.speaker is BotIdentity.CARI
    assert response.scene.text.strip()


def test_routine_director_is_deterministic() -> None:
    director = RoutineDirector()

    first = director.choose(BotIdentity.SUNNA, weekday=2, hour=20, roll=3)
    second = director.choose(BotIdentity.SUNNA, weekday=2, hour=20, roll=3)

    assert first == second


def test_routine_director_rejects_invalid_clock_values() -> None:
    director = RoutineDirector()

    with pytest.raises(ValueError):
        director.windows_for(BotIdentity.CARI, weekday=7, hour=10)
    with pytest.raises(ValueError):
        director.windows_for(BotIdentity.CARI, weekday=0, hour=24)


def test_local_social_composer_can_use_schedule_without_changing_voice() -> None:
    from app.core.social_runtime import LocalSocialComposer

    composer = LocalSocialComposer()

    morning = composer.compose(BotIdentity.CARI, roll=0, weekday=0, hour=9)
    fallback = composer.compose(BotIdentity.CARI, roll=0)

    assert morning
    assert fallback
    assert morning != fallback
