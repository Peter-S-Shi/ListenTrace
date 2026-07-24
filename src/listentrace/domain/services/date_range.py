from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# Preset keys (domain/enums intentionally not used here: these are query
# parameters, not a stored/persisted enum column).
PRESET_LAST_7_DAYS = "last_7_days"
PRESET_LAST_30_DAYS = "last_30_days"
PRESET_LAST_90_DAYS = "last_90_days"
PRESET_CUSTOM = "custom"
PRESET_ALL_TIME = "all_time"

PRESETS = (
    PRESET_LAST_7_DAYS,
    PRESET_LAST_30_DAYS,
    PRESET_LAST_90_DAYS,
    PRESET_CUSTOM,
    PRESET_ALL_TIME,
)

_PRESET_DAY_COUNTS = {
    PRESET_LAST_7_DAYS: 7,
    PRESET_LAST_30_DAYS: 30,
    PRESET_LAST_90_DAYS: 90,
}

# Every timestamp column written by this application uses SQLite's
# `datetime('now')`, which returns UTC in exactly this format (space
# separator, no 'T', no offset suffix, second precision). Bounds produced
# here must match it exactly for lexicographic comparison in SQL to work.
SQLITE_UTC_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class DateRangeError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


@dataclass(slots=True, frozen=True)
class ResolvedDateRange:
    """A resolved, half-open [start_utc, end_utc) window for filtering stored
    UTC timestamps, plus the local calendar dates it was derived from (for
    display). `start_utc`/`end_utc` are both `None` only for `all_time` —
    "no bound", never a sentinel date string that could be confused with a
    real boundary."""

    preset: str
    local_start_date: date | None
    local_end_date: date | None  # inclusive — the last local day actually included
    start_utc: str | None
    end_utc: str | None  # exclusive

    @property
    def is_bounded(self) -> bool:
        return self.start_utc is not None or self.end_utc is not None


def _local_midnight_to_utc_str(local_day: date) -> str:
    """Converts local midnight at the start of `local_day` to a UTC
    `datetime('now')`-comparable string, honoring the OS's DST rules for
    that specific date (not just "now")."""
    local_struct = (local_day.year, local_day.month, local_day.day, 0, 0, 0, 0, 0, -1)
    epoch_seconds = time.mktime(local_struct)
    utc_dt = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
    return utc_dt.strftime(SQLITE_UTC_TIMESTAMP_FORMAT)


def resolve_date_range(
    preset: str,
    today_local: date,
    *,
    custom_start_date: date | None = None,
    custom_end_date: date | None = None,
) -> ResolvedDateRange:
    """Resolve a date-range preset into UTC-comparable bounds.

    `today_local` is the caller's current local calendar date (e.g. from
    `datetime.now().date()`) — this function never reads the system clock
    itself, keeping it a pure, directly testable calculation over its inputs.

    Boundaries are always inclusive-start / exclusive-end at local midnight,
    converted to UTC per-boundary (not by applying one fixed "now" offset to
    both ends) so a range crossing a DST transition still lands on the
    correct real-world instants.
    """
    if preset not in PRESETS:
        raise DateRangeError("unknown_preset", f"Unknown date range preset: {preset!r}")

    if preset == PRESET_ALL_TIME:
        return ResolvedDateRange(preset, None, None, None, None)

    if preset == PRESET_CUSTOM:
        if custom_start_date is None or custom_end_date is None:
            raise DateRangeError(
                "missing_custom_range", "A custom range requires both a start and an end date."
            )
        if custom_end_date < custom_start_date:
            raise DateRangeError(
                "invalid_custom_range", "The custom range's end date is before its start date."
            )
        start_date, end_date_inclusive = custom_start_date, custom_end_date
    else:
        days = _PRESET_DAY_COUNTS[preset]
        end_date_inclusive = today_local
        start_date = today_local - timedelta(days=days - 1)

    start_utc = _local_midnight_to_utc_str(start_date)
    end_utc_exclusive = _local_midnight_to_utc_str(end_date_inclusive + timedelta(days=1))

    return ResolvedDateRange(preset, start_date, end_date_inclusive, start_utc, end_utc_exclusive)
