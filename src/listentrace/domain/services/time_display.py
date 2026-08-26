from __future__ import annotations

from datetime import datetime, timezone, tzinfo

from listentrace.domain.services.date_range import SQLITE_UTC_TIMESTAMP_FORMAT


def format_local_timestamp(utc_timestamp: str | None, tz: tzinfo | None = None) -> str:
    """Converts a canonical stored UTC timestamp (SQLite `datetime('now')`
    format -- see `date_range.SQLITE_UTC_TIMESTAMP_FORMAT`) to a local-time
    string for on-screen display.

    Every timestamp column in this application is persisted in UTC. This is
    the single place that performs the UTC -> local conversion for display,
    per the M12 Round 3 Time Contract ("store canonical UTC, display local
    time") -- every history/session/quiz/chart timestamp label goes through
    this function rather than interpolating the raw stored string, in the UI
    layer or (for a label string that is purely presentational, never
    re-parsed for chronological logic) directly in an application-service
    formatter.

    `tz` defaults to the host's system local zone (`.astimezone()` with no
    argument) -- the correct behavior for real display. It exists as an
    injection seam purely for deterministic, host-timezone-independent tests
    (e.g. asserting correct UTC-offset handling around a DST transition using
    a fixed `timezone(timedelta(hours=...))`), not for any real caller to
    vary the display timezone.
    """
    if not utc_timestamp:
        return ""
    utc_dt = datetime.strptime(utc_timestamp, SQLITE_UTC_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")
