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
