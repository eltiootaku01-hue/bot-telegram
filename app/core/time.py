"""Small, centralized UTC clock used at the database boundary.

Database datetime columns are currently timezone-naive, so this helper returns
UTC as a naive datetime. Keeping that policy in one place avoids mixing local
time, deprecated ``datetime.utcnow()`` calls, and timezone-aware values.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC instant as a timezone-naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
