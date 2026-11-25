"""
CITYSENSE Platform - Time and Date Utilities
"""

from datetime import datetime, timezone
from typing import Optional


def get_utc_now() -> datetime:
    """Return the current datetime in UTC timezone."""
    return datetime.now(timezone.utc)


def get_utc_iso_string(dt: Optional[datetime] = None) -> str:
    """
    Format a datetime object as an ISO-8601 string with UTC indicator.
    If dt is None, uses current UTC time.
    """
    if dt is None:
        dt = get_utc_now()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def get_current_date_str(dt: Optional[datetime] = None) -> str:
    """
    Return the date string in YYYY-MM-DD format for storage partitioning.
    """
    if dt is None:
        dt = get_utc_now()
    return dt.strftime("%Y-%m-%d")
