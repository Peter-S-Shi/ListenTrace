from __future__ import annotations

from datetime import datetime, timedelta, timezone

from listentrace.domain.services.time_display import format_local_timestamp


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


def test_offset_conversion_is_correct_across_a_dst_style_transition():
    """M14 Corrective Batch B (B1): deterministic, host-timezone-independent
    proof that the UTC-offset math is genuinely correct on both sides of a
    changing offset -- not merely applying one fixed delta everywhere, which
    is exactly the class of bug a DST transition would expose in real US/EU
    zones. Uses the `tz` injection seam (fixed `timezone(timedelta(...))`
    instances, not a real IANA zone) so this passes identically regardless of
    the machine running it or whether `tzdata` is installed."""
    from datetime import timedelta

    edt = timezone(timedelta(hours=-4), name="EDT-fixture")
    est = timezone(timedelta(hours=-5), name="EST-fixture")

    # 2026-11-01 05:30 UTC -- the moment before a hypothetical fall-back, at
    # the pre-transition offset (UTC-4).
    before_transition_utc = "2026-11-01 05:30:00"
    assert format_local_timestamp(before_transition_utc, tz=edt) == "2026-11-01 01:30"

    # The same wall-clock instant, but if this timestamp had instead been
    # produced under the post-transition offset (UTC-5) -- proves the
    # function applies whatever offset `tz` actually reports at conversion
    # time, not a single memoized delta.
    after_transition_utc = "2026-11-01 06:30:00"
    assert format_local_timestamp(after_transition_utc, tz=est) == "2026-11-01 01:30"

    # Sanity: the two UTC instants are genuinely different (1 hour apart),
    # yet both correctly land on the same local wall-clock time under their
    # respective offsets -- the real-world shape of a DST fall-back.
    assert before_transition_utc != after_transition_utc


def test_tz_argument_does_not_change_default_system_local_behavior():
    """The `tz` seam must be additive-only: every existing call site (no `tz`
    argument) keeps using the real system local zone, unchanged."""
    utc_str = "2026-01-15 12:00:00"
    utc_dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    expected = utc_dt.astimezone().strftime("%Y-%m-%d %H:%M")
    assert format_local_timestamp(utc_str) == expected
    assert format_local_timestamp(utc_str, tz=None) == expected
