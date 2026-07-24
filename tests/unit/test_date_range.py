from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from listentrace.domain.services import date_range as rules


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, rules.SQLITE_UTC_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


def test_all_time_has_no_bounds():
    resolved = rules.resolve_date_range(rules.PRESET_ALL_TIME, date(2026, 7, 24))
    assert resolved.start_utc is None
    assert resolved.end_utc is None
    assert resolved.local_start_date is None
    assert resolved.local_end_date is None
    assert not resolved.is_bounded


def test_last_7_days_spans_seven_local_calendar_days_inclusive():
    today = date(2026, 7, 24)
    resolved = rules.resolve_date_range(rules.PRESET_LAST_7_DAYS, today)
    assert resolved.local_start_date == date(2026, 7, 18)
    assert resolved.local_end_date == date(2026, 7, 24)
    assert (resolved.local_end_date - resolved.local_start_date).days == 6
    assert resolved.is_bounded


def test_last_30_and_90_days_use_the_right_day_count():
    today = date(2026, 7, 24)
    last_30 = rules.resolve_date_range(rules.PRESET_LAST_30_DAYS, today)
    last_90 = rules.resolve_date_range(rules.PRESET_LAST_90_DAYS, today)
    assert (last_30.local_end_date - last_30.local_start_date).days == 29
    assert (last_90.local_end_date - last_90.local_start_date).days == 89
    assert last_30.local_end_date == today
    assert last_90.local_end_date == today


def test_start_utc_is_before_end_utc_and_matches_sqlite_format():
    resolved = rules.resolve_date_range(rules.PRESET_LAST_7_DAYS, date(2026, 7, 24))
    assert resolved.start_utc < resolved.end_utc
    # Round-trips through the exact format sqlite's datetime('now') produces.
    _parse(resolved.start_utc)
    _parse(resolved.end_utc)


def test_end_boundary_is_exclusive_and_after_the_start_boundary():
    resolved = rules.resolve_date_range(rules.PRESET_LAST_7_DAYS, date(2026, 7, 24))
    start_dt = _parse(resolved.start_utc)
    end_dt = _parse(resolved.end_utc)
    assert end_dt > start_dt
    # 7 local calendar days apart — real elapsed hours may differ from exactly
    # 7*24h across a DST transition, but the day count itself must not drift.
    assert 6 * 24 * 3600 <= (end_dt - start_dt).total_seconds() <= 8 * 24 * 3600


def test_custom_range_uses_the_given_dates():
    resolved = rules.resolve_date_range(
        rules.PRESET_CUSTOM,
        date(2026, 7, 24),
        custom_start_date=date(2026, 1, 1),
        custom_end_date=date(2026, 1, 31),
    )
    assert resolved.local_start_date == date(2026, 1, 1)
    assert resolved.local_end_date == date(2026, 1, 31)


def test_custom_range_requires_both_dates():
    with pytest.raises(rules.DateRangeError) as exc_info:
        rules.resolve_date_range(rules.PRESET_CUSTOM, date(2026, 7, 24), custom_start_date=date(2026, 1, 1))
    assert exc_info.value.category == "missing_custom_range"


def test_custom_range_rejects_end_before_start():
    with pytest.raises(rules.DateRangeError) as exc_info:
        rules.resolve_date_range(
            rules.PRESET_CUSTOM,
            date(2026, 7, 24),
            custom_start_date=date(2026, 1, 31),
            custom_end_date=date(2026, 1, 1),
        )
    assert exc_info.value.category == "invalid_custom_range"


def test_unknown_preset_is_rejected():
    with pytest.raises(rules.DateRangeError) as exc_info:
        rules.resolve_date_range("last_week", date(2026, 7, 24))
    assert exc_info.value.category == "unknown_preset"


def test_single_day_custom_range_still_has_a_positive_span():
    resolved = rules.resolve_date_range(
        rules.PRESET_CUSTOM,
        date(2026, 7, 24),
        custom_start_date=date(2026, 3, 5),
        custom_end_date=date(2026, 3, 5),
    )
    start_dt = _parse(resolved.start_utc)
    end_dt = _parse(resolved.end_utc)
    assert end_dt > start_dt
    assert (end_dt - start_dt).total_seconds() == 86400
