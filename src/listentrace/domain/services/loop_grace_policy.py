from __future__ import annotations

# Pure, framework-free authoritative definition of the Loop End Grace product
# contract (see CONTEXT.md). Single source of truth: persistence, the resolver
# service, and the Settings UI all import these rather than each defining their
# own magic numbers. The database is never the authoritative source of the
# default -- if a persisted global-default row is ever unexpectedly missing,
# the resolver falls back to LOOP_END_GRACE_DEFAULT_MS from here.

LOOP_END_GRACE_MIN_MS = 60
LOOP_END_GRACE_MAX_MS = 300
LOOP_END_GRACE_DEFAULT_MS = 180
LOOP_END_GRACE_STEP_MS = 10  # UI-only concern, kept here anyway: one authoritative location


def is_valid_loop_end_grace_ms(value: int) -> bool:
    return LOOP_END_GRACE_MIN_MS <= value <= LOOP_END_GRACE_MAX_MS


def clamp_loop_end_grace_ms(value: int) -> int:
    """Defensive backstop against already-persisted out-of-range data. Not the
    primary defense -- `loop_grace_service` rejects invalid values at write
    time; this only protects a read against data that got in some other way
    (a future migration issue, a manual DB edit)."""
    return max(LOOP_END_GRACE_MIN_MS, min(LOOP_END_GRACE_MAX_MS, value))


def snap_to_slider_step_ms(value: int) -> int:
    """Round `value` to the nearest `LOOP_END_GRACE_STEP_MS` increment,
    anchored at `LOOP_END_GRACE_MIN_MS`. For slider-originated input only --
    `QSlider.singleStep`/`pageStep` govern keyboard/wheel increments but not
    a mouse drag, which can land on any integer in range. The numeric
    spinbox is unaffected by this: it accepts any integer 60-300 exactly,
    per the frozen contract's `10ms is adjustment granularity only`."""
    # Round-half-up, not Python's round-half-to-even: `round()` would send an
    # exact-tie value (e.g. 185, equidistant between 180 and 190) down on an
    # even quotient, which is a surprising/arbitrary direction for a UI
    # control with no other guidance biasing it either way.
    steps = (value - LOOP_END_GRACE_MIN_MS + LOOP_END_GRACE_STEP_MS // 2) // LOOP_END_GRACE_STEP_MS
    snapped = LOOP_END_GRACE_MIN_MS + steps * LOOP_END_GRACE_STEP_MS
    return clamp_loop_end_grace_ms(snapped)
