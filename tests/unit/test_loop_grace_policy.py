from __future__ import annotations

from listentrace.domain.services import loop_grace_policy as policy


def test_bounds_and_default_match_the_frozen_product_contract():
    assert policy.LOOP_END_GRACE_MIN_MS == 60
    assert policy.LOOP_END_GRACE_MAX_MS == 300
    assert policy.LOOP_END_GRACE_DEFAULT_MS == 180
    assert policy.LOOP_END_GRACE_STEP_MS == 10


def test_default_is_within_bounds():
    assert policy.LOOP_END_GRACE_MIN_MS <= policy.LOOP_END_GRACE_DEFAULT_MS <= policy.LOOP_END_GRACE_MAX_MS


def test_is_valid_accepts_the_full_inclusive_range():
    assert policy.is_valid_loop_end_grace_ms(60) is True
    assert policy.is_valid_loop_end_grace_ms(180) is True
    assert policy.is_valid_loop_end_grace_ms(300) is True


def test_is_valid_rejects_outside_the_range():
    assert policy.is_valid_loop_end_grace_ms(59) is False
    assert policy.is_valid_loop_end_grace_ms(301) is False
    assert policy.is_valid_loop_end_grace_ms(0) is False


def test_clamp_leaves_in_range_values_untouched():
    assert policy.clamp_loop_end_grace_ms(180) == 180
    assert policy.clamp_loop_end_grace_ms(60) == 60
    assert policy.clamp_loop_end_grace_ms(300) == 300


def test_clamp_pulls_out_of_range_values_to_the_nearest_bound():
    """The backstop defense against already-persisted out-of-range data
    (e.g. a future migration issue or a manual DB edit) -- write-time
    rejection is the primary defense; this is the second line."""
    assert policy.clamp_loop_end_grace_ms(0) == 60
    assert policy.clamp_loop_end_grace_ms(-500) == 60
    assert policy.clamp_loop_end_grace_ms(301) == 300
    assert policy.clamp_loop_end_grace_ms(999999) == 300


# ---- snap_to_slider_step_ms: slider-originated input only, never the spinbox ----


def test_snap_leaves_exact_multiples_of_the_step_untouched():
    assert policy.snap_to_slider_step_ms(60) == 60
    assert policy.snap_to_slider_step_ms(180) == 180
    assert policy.snap_to_slider_step_ms(300) == 300


def test_snap_rounds_to_the_nearest_ten():
    assert policy.snap_to_slider_step_ms(183) == 180
    assert policy.snap_to_slider_step_ms(186) == 190
    assert policy.snap_to_slider_step_ms(64) == 60
    assert policy.snap_to_slider_step_ms(66) == 70


def test_snap_rounds_a_tie_up():
    assert policy.snap_to_slider_step_ms(185) == 190


def test_snap_result_stays_within_bounds():
    assert policy.snap_to_slider_step_ms(61) == 60
    assert policy.snap_to_slider_step_ms(298) == 300
