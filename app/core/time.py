"""Centralized clock helpers for UTC storage and world-local scheduling."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Return the current UTC instant as a timezone-naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def localize_utc(utc_datetime: datetime, timezone_name: str) -> datetime:
    """Convert a naive UTC datetime into a naive datetime in ``timezone_name``.

    Storage remains UTC-naive; scheduling may use an explicit IANA timezone.
    """
    if not timezone_name.strip():
        raise ValueError("timezone_name must not be empty")
    aware_utc = utc_datetime.replace(tzinfo=timezone.utc)
    return aware_utc.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)


def world_now(timezone_name: str) -> datetime:
    """Return the current instant expressed in the configured world timezone."""
    return localize_utc(utc_now(), timezone_name)


def local_to_utc(local_datetime: datetime, timezone_name: str) -> datetime:
    """Convert a naive world-local datetime into a naive UTC datetime for storage."""
    if not timezone_name.strip():
        raise ValueError("timezone_name must not be empty")
    aware_local = local_datetime.replace(tzinfo=ZoneInfo(timezone_name))
    return aware_local.astimezone(timezone.utc).replace(tzinfo=None)
