from __future__ import annotations

from listentrace.application.dto.player_state import LoopMode
from listentrace.application.services.player_session import (
    LOOP_END_TOLERANCE_MS,
    PlayerSession,
)
from listentrace.domain.models.subtitle import SubtitleCue


def _cue(index, start, end, text="x"):
    return SubtitleCue(cue_index=index, start_ms=start, end_ms=end, text=text)


def _cues():
    return [_cue(1, 0, 1000, "one"), _cue(2, 1000, 2000, "two"), _cue(3, 2000, 3000, "three")]


def test_transcript_visible_defaults_true():
    session = PlayerSession(_cues())
    assert session.transcript_visible is True


def test_replay_cue_pauses_once_at_cue_end_and_does_not_loop():
    session = PlayerSession(_cues())
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


def test_play_cue_starts_at_cue_start_when_never_played():
    session = PlayerSession(_cues())
    seek_to = session.play_cue(1)  # cue "two": 1000-2000
    assert seek_to == 1000


def test_play_cue_resumes_in_place_when_paused_mid_cue():
    session = PlayerSession(_cues())
    session.play_cue(1)  # start cue "two"
    session.on_position_changed(1400)  # learner paused here, mid-cue

    seek_to = session.play_cue(1)  # pressed Play again
    assert seek_to is None, "must resume from 1400ms, not restart at cue.start"


def test_play_cue_restarts_at_cue_start_once_it_already_reached_cue_end():
    session = PlayerSession(_cues())
    session.play_cue(1)  # cue "two": 1000-2000
    tick = session.on_position_changed(2000)
    assert tick.pause is True  # naturally reached cue.end and stopped

    seek_to = session.play_cue(1)  # pressed Play again after it finished
    assert seek_to == 1000, "a second press after natural completion must replay from the start"


def test_play_cue_never_drifts_past_cue_end():
    session = PlayerSession(_cues())
    session.play_cue(0)  # cue "one": 0-1000
    tick = session.on_position_changed(1000)
    assert tick.pause is True
    tick = session.on_position_changed(1500)
    assert tick.pause is False  # one-shot: no further pause/restart once already stopped


# ---- Loop as repeated one-shot replay of a span (M12 Round 3) ----
#
# A Loop iteration reaching its end is the exact same primitive as Replay Cue
# reaching its end: `pause=True`, always. The only thing that differs is
# whether `restart_at_ms` also comes back, telling the caller to begin a new
# one-shot span at the same start -- never an immediate reposition while
# still playing, and never a bare "seek" outcome distinct from "pause."


def test_loop_cue_schedules_a_restart_of_the_same_span_at_cue_end():
    session = PlayerSession(_cues())
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
    session = PlayerSession(_cues())
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
    session = PlayerSession(_cues())
    session.loop_cue(1)  # cue "two": 1000-2000

    tick = session.on_position_changed(2300)
    assert tick.restart_at_ms == 1000


def test_repeated_ticks_after_scheduling_a_restart_do_not_reschedule_again():
    """The pending debounce must suppress repeated completion detection while
    a restart has already been scheduled and hasn't landed yet (stale ticks
    still reporting a position near the old end)."""
    session = PlayerSession(_cues())
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
    session = PlayerSession(_cues())
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
    session = PlayerSession(_cues())
    session.loop_range(2, 0)
    assert session.selected_range == (0, 2)


def test_cancel_loop_stops_future_completions_of_the_old_span():
    session = PlayerSession(_cues())
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
    session = PlayerSession(_cues())
    session.loop_cue(1)  # cue "two": 1000-2000
    scheduled = session.on_position_changed(2000)
    assert scheduled.restart_at_ms == 1000

    session.cancel_loop()

    tick = session.on_position_changed(2000)
    assert tick.pause is False
    assert tick.restart_at_ms is None


def test_starting_a_loop_cancels_any_pending_replay():
    session = PlayerSession(_cues())
    session.replay_cue(0)
    session.loop_cue(1)

    tick = session.on_position_changed(1000)  # would have been the replay's pause point
    assert tick.pause is False


def test_active_cue_index_tracks_position_regardless_of_transcript_visibility():
    session = PlayerSession(_cues())
    session.transcript_visible = False
    tick = session.on_position_changed(1500)
    assert tick.active_cue_index == 1
    assert session.active_cue_index == 1


def test_previous_and_next_cue_delegate_to_cue_index():
    session = PlayerSession(_cues())
    assert session.next_cue_index(0) == 1
    assert session.previous_cue_index(1) == 0
