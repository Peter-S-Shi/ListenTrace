from __future__ import annotations

from datetime import datetime, timezone

from listentrace.domain.services.date_range import SQLITE_UTC_TIMESTAMP_FORMAT


def format_local_timestamp(utc_timestamp: str | None) -> str:
    """Converts a canonical stored UTC timestamp (SQLite `datetime('now')`
    format -- see `date_range.SQLITE_UTC_TIMESTAMP_FORMAT`) to a local-time
    string for on-screen display.

    Every timestamp column in this application is persisted in UTC. This is
    the single place that performs the UTC -> local conversion for display,
    per the M12 Round 3 Time Contract ("store canonical UTC, display local
    time") -- every history/session/quiz timestamp label should go through
    this function rather than interpolating the raw stored string.
    """
    if not utc_timestamp:
        return ""
    utc_dt = datetime.strptime(utc_timestamp, SQLITE_UTC_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    return utc_dt.astimezone().strftime("%Y-%m-%d %H:%M")
