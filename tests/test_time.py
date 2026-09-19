from datetime import datetime, timezone

import pytest

from app.core.time import local_to_utc, localize_utc


def test_localize_utc_uses_configured_world_timezone() -> None:
    utc = datetime(2026, 1, 15, 12, 0, 0)

    local = localize_utc(utc, "America/Argentina/Buenos_Aires")

    assert local == datetime(2026, 1, 15, 9, 0, 0)


def test_localize_utc_rejects_empty_timezone() -> None:
    try:
        localize_utc(datetime(2026, 1, 15, 12, 0, 0), "")
    except ValueError as exc:
        assert "timezone_name" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_local_to_utc_converts_world_schedule_for_storage() -> None:
    local = datetime(2026, 1, 15, 9, 0, 0)

    utc = local_to_utc(local, "America/Argentina/Buenos_Aires")

    assert utc == datetime(2026, 1, 15, 12, 0, 0)


def test_local_to_utc_rejects_empty_timezone() -> None:
    try:
        local_to_utc(datetime(2026, 1, 15, 12, 0, 0), "")
    except ValueError as exc:
        assert "timezone_name" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_localize_utc_rejects_timezone_aware_input() -> None:
    aware = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timezone-naive"):
        localize_utc(aware, "America/Argentina/Buenos_Aires")


def test_local_to_utc_rejects_timezone_aware_input() -> None:
    aware = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timezone-naive"):
        local_to_utc(aware, "America/Argentina/Buenos_Aires")
