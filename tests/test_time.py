from datetime import datetime

from app.core.time import localize_utc


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
