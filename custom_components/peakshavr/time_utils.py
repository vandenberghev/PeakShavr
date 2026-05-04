"""Quarter and month time helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BELGIUM_TIME_ZONE = ZoneInfo("Europe/Brussels")
QUARTER_SECONDS = 15 * 60


def as_belgium_time(moment: datetime) -> datetime:
    """Convert datetime to Europe/Brussels timezone."""
    if moment.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware")
    return moment.astimezone(BELGIUM_TIME_ZONE)


def quarter_start(moment: datetime) -> datetime:
    """Return quarter start in Europe/Brussels time."""
    local = as_belgium_time(moment)
    floored_minute = (local.minute // 15) * 15
    return local.replace(minute=floored_minute, second=0, microsecond=0)


def next_quarter_start(moment: datetime) -> datetime:
    """Return next quarter boundary in Europe/Brussels time."""
    start = quarter_start(moment)
    return start + timedelta(minutes=15)


def quarter_elapsed_and_remaining_seconds(moment: datetime) -> tuple[int, int]:
    """Return elapsed and remaining seconds for current quarter."""
    local = as_belgium_time(moment)
    start = quarter_start(local)
    elapsed = int((local - start).total_seconds())
    elapsed = max(0, min(QUARTER_SECONDS, elapsed))
    return elapsed, QUARTER_SECONDS - elapsed


def quarter_key(moment: datetime) -> str:
    """Stable quarter key for persistence."""
    return quarter_start(moment).isoformat()


def month_key(moment: datetime) -> str:
    """Return local month key in YYYY-MM format."""
    local = as_belgium_time(moment)
    return f"{local.year:04d}-{local.month:02d}"

