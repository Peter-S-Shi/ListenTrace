from __future__ import annotations

from datetime import datetime, timedelta, timezone

from listentrace.ui.time_display import format_local_timestamp


def test_empty_or_missing_input_returns_empty_string():
    assert format_local_timestamp(None) == ""
    assert format_local_timestamp("") == ""


def test_converts_stored_utc_to_the_system_local_wall_clock():
    utc_str = "2026-01-15 12:00:00"
    utc_dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    expected = utc_dt.astimezone().strftime("%Y-%m-%d %H:%M")
    assert format_local_timestamp(utc_str) == expected


def test_differs_from_the_raw_stored_string_whenever_local_is_not_utc():
    """M12 Round 3 Time Contract regression: the whole point of this helper is
    that history/session displays must stop showing the raw UTC string
    verbatim. Skips only on a system whose local zone genuinely is UTC."""
    utc_str = "2026-01-15 12:00:00"
    local_offset = datetime.now().astimezone().utcoffset()
    if local_offset == timedelta(0):
        return
    assert format_local_timestamp(utc_str) != "2026-01-15 12:00"
