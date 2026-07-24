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

    tick = session.on_position_changed(1000 - LOOP_END_TOLERANCE_MS - 1)
    assert tick.pause is False

    tick = session.on_position_changed(1000 - LOOP_END_TOLERANCE_MS)
    assert tick.pause is True

    # replay is one-shot: further ticks must not pause or seek again
    tick = session.on_position_changed(1500)
    assert tick.pause is False
    assert tick.seek_to_ms is None


def test_loop_cue_seeks_back_to_start_at_cue_end():
    session = PlayerSession(_cues())
    seek_to = session.loop_cue(1)  # cue "two": 1000-2000
    assert seek_to == 1000
    assert session.loop_mode is LoopMode.CUE

    tick = session.on_position_changed(1500)
    assert tick.seek_to_ms is None

    tick = session.on_position_changed(2000 - LOOP_END_TOLERANCE_MS)
    assert tick.seek_to_ms == 1000

    # while the seek is "pending", further ticks near the boundary must not re-trigger
    tick = session.on_position_changed(2000 - LOOP_END_TOLERANCE_MS)
    assert tick.seek_to_ms is None

    # once position reflects the completed seek, the loop can trigger again next time
    tick = session.on_position_changed(1000)
    assert tick.seek_to_ms is None
    tick = session.on_position_changed(2000 - LOOP_END_TOLERANCE_MS)
    assert tick.seek_to_ms == 1000


def test_loop_range_spans_first_to_last_selected_cue():
    session = PlayerSession(_cues())
    seek_to = session.loop_range(0, 2)
    assert seek_to == 0
    assert session.loop_mode is LoopMode.RANGE
    assert session.selected_range == (0, 2)

    tick = session.on_position_changed(3000 - LOOP_END_TOLERANCE_MS)
    assert tick.seek_to_ms == 0


def test_loop_range_normalizes_reversed_selection():
    session = PlayerSession(_cues())
    session.loop_range(2, 0)
    assert session.selected_range == (0, 2)


def test_cancel_loop_stops_boundary_seeks():
    session = PlayerSession(_cues())
    session.loop_cue(0)
    session.cancel_loop()
    assert session.loop_mode is LoopMode.NONE

    tick = session.on_position_changed(1000 - LOOP_END_TOLERANCE_MS)
    assert tick.seek_to_ms is None


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
