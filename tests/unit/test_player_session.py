from __future__ import annotations

from listentrace.application.dto.player_state import LoopMode
from listentrace.application.services.player_session import (
    LOOP_END_TOLERANCE_MS,
    PlayerSession,
)
from listentrace.domain.models.subtitle import SubtitleCue

DEFAULT_LOOP_END_GRACE_MS = 180


def _cue(index, start, end, text="x"):
    return SubtitleCue(cue_index=index, start_ms=start, end_ms=end, text=text)


def _cues():
    return [_cue(1, 0, 1000, "one"), _cue(2, 1000, 2000, "two"), _cue(3, 2000, 3000, "three")]


def _session(cues, loop_end_grace_ms=DEFAULT_LOOP_END_GRACE_MS):
    return PlayerSession(cues, loop_end_grace_ms=loop_end_grace_ms)


def test_transcript_visible_defaults_true():
    session = _session(_cues())
    assert session.transcript_visible is True


def test_replay_cue_pauses_once_at_cue_end_and_does_not_loop():
    session = _session(_cues())
    seek_to = session.replay_cue(0)
    assert seek_to == 0

    tick = session.on_position_changed(1000 - 1)
    assert tick.pause is False

    tick = session.on_position_changed(1000)
    assert tick.pause is True
    assert tick.restart_at_ms is None, "Replay is one-shot: it must never carry a restart"

    # replay is one-shot: further ticks must not pause or restart again
    tick = session.on_position_changed(1500)
    assert tick.pause is False
    assert tick.restart_at_ms is None


def test_replay_cue_completion_is_unaffected_by_a_large_grace():
    """Grace only extends a Loop's effective completion end -- Replay Cue's
    logical end is exactly `span.end_ms`, regardless of the configured grace."""
    session = _session(_cues(), loop_end_grace_ms=300)
    session.replay_cue(0)  # cue "one": 0-1000

    tick = session.on_position_changed(1000)
    assert tick.pause is True, "Replay must complete at the cue's own end, not end + grace"


def test_play_cue_starts_at_cue_start_when_never_played():
    session = _session(_cues())
    seek_to = session.play_cue(1)  # cue "two": 1000-2000
    assert seek_to == 1000


def test_play_cue_resumes_in_place_when_paused_mid_cue():
    session = _session(_cues())
    session.play_cue(1)  # start cue "two"
    session.on_position_changed(1400)  # learner paused here, mid-cue

    seek_to = session.play_cue(1)  # pressed Play again
    assert seek_to is None, "must resume from 1400ms, not restart at cue.start"


def test_play_cue_restarts_at_cue_start_once_it_already_reached_cue_end():
    session = _session(_cues())
    session.play_cue(1)  # cue "two": 1000-2000
    tick = session.on_position_changed(2000)
    assert tick.pause is True  # naturally reached cue.end and stopped

    seek_to = session.play_cue(1)  # pressed Play again after it finished
    assert seek_to == 1000, "a second press after natural completion must replay from the start"


def test_play_cue_never_drifts_past_cue_end():
    session = _session(_cues())
    session.play_cue(0)  # cue "one": 0-1000
    tick = session.on_position_changed(1000)
    assert tick.pause is True
    tick = session.on_position_changed(1500)
    assert tick.pause is False  # one-shot: no further pause/restart once already stopped


def test_play_cue_completion_is_unaffected_by_a_large_grace():
    session = _session(_cues(), loop_end_grace_ms=300)
    session.play_cue(0)  # cue "one": 0-1000

    tick = session.on_position_changed(1000)
    assert tick.pause is True, "Play-cue must complete at the cue's own end, not end + grace"


# ---- Loop as repeated one-shot replay of a span (M12 Round 3) ----
#
# A Loop iteration reaching its end is the exact same primitive as Replay Cue
# reaching its end: `pause=True`, always. The only thing that differs is
# whether `restart_at_ms` also comes back, telling the caller to begin a new
# one-shot span at the same start -- never an immediate reposition while
# still playing, and never a bare "seek" outcome distinct from "pause."


def test_loop_cue_schedules_a_restart_of_the_same_span_at_cue_end():
    session = _session(_cues(), loop_end_grace_ms=0)
    seek_to = session.loop_cue(1)  # cue "two": 1000-2000
    assert seek_to == 1000
    assert session.loop_mode is LoopMode.CUE

    tick = session.on_position_changed(1500)
    assert tick.pause is False
    assert tick.restart_at_ms is None

    tick = session.on_position_changed(2000)
    assert tick.pause is True
    assert tick.restart_at_ms == 1000


def test_loop_cue_does_not_restart_before_the_cue_actually_ends():
    """DIAG-8f31 (Round 1): the original boundary check subtracted
    LOOP_END_TOLERANCE_MS from the target *before* comparing, so completion
    fired up to 50ms early on every repetition -- a guaranteed, audible
    truncation, not merely a defensive margin (`>=` already tolerates a
    late/coarse tick landing past the target)."""
    session = _session(_cues(), loop_end_grace_ms=0)
    session.loop_cue(1)  # cue "two": 1000-2000

    tick = session.on_position_changed(2000 - LOOP_END_TOLERANCE_MS)
    assert tick.restart_at_ms is None, "must not truncate the cue's own tail before its real end"

    tick = session.on_position_changed(1999)
    assert tick.restart_at_ms is None

    tick = session.on_position_changed(2000)
    assert tick.restart_at_ms == 1000


def test_loop_cue_still_completes_when_a_coarse_tick_overshoots_the_end():
    """A tick landing past the boundary (coarse update cadence) must still
    trigger completion -- robustness does not depend on an early-margin
    subtraction, `>=` already covers overshoot."""
    session = _session(_cues(), loop_end_grace_ms=0)
    session.loop_cue(1)  # cue "two": 1000-2000

    tick = session.on_position_changed(2300)
    assert tick.restart_at_ms == 1000


def test_repeated_ticks_after_scheduling_a_restart_do_not_reschedule_again():
    """The pending debounce must suppress repeated completion detection while
    a restart has already been scheduled and hasn't landed yet (stale ticks
    still reporting a position near the old end)."""
    session = _session(_cues(), loop_end_grace_ms=0)
    session.loop_cue(1)  # cue "two": 1000-2000

    first = session.on_position_changed(2000)
    assert first.restart_at_ms == 1000

    again = session.on_position_changed(2000)
    assert again.pause is False
    assert again.restart_at_ms is None

    # once position reflects the completed restart, the span can complete again
    landed = session.on_position_changed(1000)
    assert landed.restart_at_ms is None
    next_cycle = session.on_position_changed(2000)
    assert next_cycle.restart_at_ms == 1000


def test_loop_range_treats_the_entire_selection_as_one_indivisible_span():
    """Loop Range must never fire a completion at any *internal* cue boundary
    inside the selection -- only at the end of the last selected cue. Cue
    "two" (1000-2000ms) sits entirely inside the range and must produce no
    tick at all resembling completion."""
    session = _session(_cues(), loop_end_grace_ms=0)
    seek_to = session.loop_range(0, 2)  # cues 0-2: 0-3000ms as one span
    assert seek_to == 0
    assert session.loop_mode is LoopMode.RANGE
    assert session.selected_range == (0, 2)

    # the internal boundary between cue 0 and cue 1 (1000ms) must not complete
    at_internal_boundary = session.on_position_changed(1000)
    assert at_internal_boundary.pause is False
    assert at_internal_boundary.restart_at_ms is None

    # nor the internal boundary between cue 1 and cue 2 (2000ms)
    at_second_internal_boundary = session.on_position_changed(2000)
    assert at_second_internal_boundary.pause is False
    assert at_second_internal_boundary.restart_at_ms is None

    # only the end of the *entire selected range* (cue 2's end, 3000ms) completes
    at_range_end = session.on_position_changed(3000)
    assert at_range_end.pause is True
    assert at_range_end.restart_at_ms == 0


def test_loop_range_normalizes_reversed_selection():
    session = _session(_cues())
    session.loop_range(2, 0)
    assert session.selected_range == (0, 2)


def test_cancel_loop_stops_future_completions_of_the_old_span():
    session = _session(_cues(), loop_end_grace_ms=0)
    session.loop_cue(0)
    session.cancel_loop()
    assert session.loop_mode is LoopMode.NONE

    tick = session.on_position_changed(1000)
    assert tick.pause is False
    assert tick.restart_at_ms is None


def test_cancel_loop_during_a_pending_restart_prevents_it_from_completing_again():
    """If Loop is cancelled in the brief window after a restart has been
    scheduled but before a position tick confirms it landed, no further
    completion may fire for the old span."""
    session = _session(_cues(), loop_end_grace_ms=0)
    session.loop_cue(1)  # cue "two": 1000-2000
    scheduled = session.on_position_changed(2000)
    assert scheduled.restart_at_ms == 1000

    session.cancel_loop()

    tick = session.on_position_changed(2000)
    assert tick.pause is False
    assert tick.restart_at_ms is None


def test_starting_a_loop_cancels_any_pending_replay():
    session = _session(_cues())
    session.replay_cue(0)
    session.loop_cue(1)

    tick = session.on_position_changed(1000)  # would have been the replay's pause point
    assert tick.pause is False


def test_active_cue_index_tracks_position_regardless_of_transcript_visibility():
    session = _session(_cues())
    session.transcript_visible = False
    tick = session.on_position_changed(1500)
    assert tick.active_cue_index == 1
    assert session.active_cue_index == 1


def test_previous_and_next_cue_delegate_to_cue_index():
    session = _session(_cues())
    assert session.next_cue_index(0) == 1
    assert session.previous_cue_index(1) == 0


# ---- Loop End Grace (M12 Loop End Grace / Candidate 2) ----
#
# `loop_end_grace_ms` extends a Loop iteration's *effective completion end*
# (span.end_ms + grace) -- it never mutates the span's own logical end, and
# it never applies to Replay Cue or Play-cue (covered above).


def test_loop_cue_completion_waits_for_grace_past_the_cue_end():
    session = _session(_cues(), loop_end_grace_ms=180)
    session.loop_cue(1)  # cue "two": logical end 2000ms

    still_within_grace = session.on_position_changed(2179)
    assert still_within_grace.pause is False
    assert still_within_grace.restart_at_ms is None, "must not complete before end + grace"

    at_effective_end = session.on_position_changed(2180)
    assert at_effective_end.pause is True
    assert at_effective_end.restart_at_ms == 1000, "restart still targets the span's own start"


def test_loop_range_completion_grace_applies_only_once_at_the_final_range_end():
    """Grace must attach only to the range's own final effective completion
    end -- never to any internal cue boundary, which must stay structurally
    inert exactly as it is without grace."""
    session = _session(_cues(), loop_end_grace_ms=180)
    session.loop_range(0, 2)  # 0-3000ms as one span

    at_internal_boundary_plus_grace = session.on_position_changed(1180)
    assert at_internal_boundary_plus_grace.pause is False
    assert at_internal_boundary_plus_grace.restart_at_ms is None

    before_effective_range_end = session.on_position_changed(3179)
    assert before_effective_range_end.restart_at_ms is None

    at_effective_range_end = session.on_position_changed(3180)
    assert at_effective_range_end.pause is True
    assert at_effective_range_end.restart_at_ms == 0


def test_zero_grace_completes_exactly_at_the_logical_end_as_before():
    session = _session(_cues(), loop_end_grace_ms=0)
    session.loop_cue(1)  # cue "two": 1000-2000
    tick = session.on_position_changed(2000)
    assert tick.restart_at_ms == 1000


# ---- on_media_ended (M12 Loop End Grace / Candidate 2) ----
#
# The second of the two legal ways a bounded playback span completes: the
# underlying media's physical end arrives before any position tick ever
# crosses the effective completion end (e.g. grace pushes the threshold past
# the Material's actual duration, or any cue's logical end already exceeds
# it). Shares the same completion outcome as `on_position_changed`.


def test_on_media_ended_with_no_active_span_is_a_no_op():
    session = _session(_cues())
    tick = session.on_media_ended()
    assert tick.pause is False
    assert tick.restart_at_ms is None


def test_on_media_ended_completes_a_pending_replay_cue_and_clears_the_span():
    session = _session(_cues())
    session.replay_cue(0)  # cue "one": 0-1000, media ends at e.g. 700ms

    tick = session.on_media_ended()
    assert tick.pause is True
    assert tick.restart_at_ms is None, "Replay is one-shot: no restart even via EndOfMedia"

    # span is cleared: a further tick must not pause/restart again
    again = session.on_media_ended()
    assert again.pause is False


def test_on_media_ended_sets_play_cue_reached_end_so_a_second_press_restarts():
    session = _session(_cues())
    session.play_cue(1)  # cue "two": 1000-2000, media ends before 2000ms

    session.on_media_ended()
    seek_to = session.play_cue(1)  # pressed Play again
    assert seek_to == 1000, "EOF-driven completion must set reached-end just like a tick would"


def test_on_media_ended_completes_a_loop_iteration_and_produces_a_restart():
    session = _session(_cues(), loop_end_grace_ms=180)
    session.loop_cue(1)  # cue "two": 1000-2000, effective end 2180ms exceeds media duration

    tick = session.on_media_ended()
    assert tick.pause is True
    assert tick.restart_at_ms == 1000, "Loop must still restart even when EOF preempts the tick path"


def test_on_media_ended_is_a_no_op_while_a_tick_driven_restart_is_already_pending():
    """If a position tick already completed this iteration and a restart is
    already scheduled, a subsequent EndOfMedia for the same iteration must
    not trigger a second, redundant completion."""
    session = _session(_cues(), loop_end_grace_ms=0)
    session.loop_cue(1)  # cue "two": 1000-2000
    scheduled = session.on_position_changed(2000)
    assert scheduled.restart_at_ms == 1000

    redundant = session.on_media_ended()
    assert redundant.pause is False
    assert redundant.restart_at_ms is None


# ---- set_loop_end_grace_ms: next-iteration-only effect (Batch C) ----
#
# A live change must never move the effective completion end of a Loop
# iteration already in flight -- only the iteration that begins after the
# current one completes and restarts may use it.


def test_set_loop_end_grace_ms_does_not_move_the_in_flight_iterations_threshold():
    session = _session(_cues(), loop_end_grace_ms=180)
    session.loop_cue(1)  # cue "two": logical end 2000ms, effective end 2180ms

    session.set_loop_end_grace_ms(70)  # learner drags the slider mid-iteration

    still_using_old_threshold = session.on_position_changed(2071)
    assert still_using_old_threshold.pause is False
    assert still_using_old_threshold.restart_at_ms is None, (
        "the iteration already playing must keep using 180ms, not jump to 70ms"
    )

    at_old_effective_end = session.on_position_changed(2180)
    assert at_old_effective_end.restart_at_ms == 1000, "still completes at the OLD effective end"


def test_set_loop_end_grace_ms_applies_starting_the_next_iteration():
    session = _session(_cues(), loop_end_grace_ms=180)
    session.loop_cue(1)  # cue "two": 1000-2000
    session.set_loop_end_grace_ms(70)

    completed = session.on_position_changed(2180)  # old threshold, iteration completes
    assert completed.restart_at_ms == 1000

    # the restart "lands": position drops back below the (now-clearing)
    # pending debounce, confirming the next iteration has genuinely begun
    landed = session.on_position_changed(1000)
    assert landed.restart_at_ms is None

    next_iteration = session.on_position_changed(2070)  # new 70ms effective end
    assert next_iteration.pause is True
    assert next_iteration.restart_at_ms == 1000, "the next iteration now uses the new 70ms grace"


def test_set_loop_end_grace_ms_before_looping_at_all_is_just_the_starting_value():
    session = _session(_cues(), loop_end_grace_ms=180)
    session.set_loop_end_grace_ms(60)
    session.loop_cue(1)  # cue "two": 1000-2000

    tick = session.on_position_changed(2060)
    assert tick.restart_at_ms == 1000


def test_set_loop_end_grace_ms_does_not_affect_replay_cue_or_play_cue():
    session = _session(_cues(), loop_end_grace_ms=180)
    session.replay_cue(0)  # cue "one": 0-1000
    session.set_loop_end_grace_ms(300)

    tick = session.on_position_changed(1000)
    assert tick.pause is True, "Replay must still complete at the bare logical end"


def test_starting_a_new_loop_snapshots_whatever_grace_is_live_at_that_moment():
    session = _session(_cues(), loop_end_grace_ms=180)
    session.set_loop_end_grace_ms(250)  # changed before any loop ever started

    session.loop_cue(1)  # cue "two": 1000-2000
    tick = session.on_position_changed(2250)
    assert tick.restart_at_ms == 1000
