from __future__ import annotations

from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.domain.services.cue_index import CueIndex


def _cue(index, start, end, text="x"):
    return SubtitleCue(cue_index=index, start_ms=start, end_ms=end, text=text)


def test_active_cue_at_exact_start():
    index = CueIndex([_cue(1, 1000, 2000)])
    assert index.active_cue_index(1000) == 0


def test_cue_inactive_at_exact_end():
    index = CueIndex([_cue(1, 1000, 2000)])
    assert index.active_cue_index(2000) is None


def test_no_active_cue_during_gap():
    index = CueIndex([_cue(1, 0, 1000), _cue(2, 2000, 3000)])
    assert index.active_cue_index(1500) is None


def test_no_active_cue_before_first_cue():
    index = CueIndex([_cue(1, 1000, 2000)])
    assert index.active_cue_index(500) is None


def test_overlapping_cues_select_latest_started_active_cue():
    # cue A: 0-1000, cue B: 500-600 (nested)
    index = CueIndex([_cue(1, 0, 1000, "A"), _cue(2, 500, 600, "B")])

    # inside both -> latest start (B) wins
    assert index.cues[index.active_cue_index(550)].text == "B"

    # after B ends but A still active -> falls back to A
    assert index.cues[index.active_cue_index(700)].text == "A"


def test_original_order_preserved_for_navigation_regardless_of_start_order():
    # deliberately out-of-order starts in the cue list itself
    index = CueIndex([_cue(2, 2000, 3000, "second"), _cue(1, 0, 1000, "first")])
    assert index.cues[0].text == "second"
    assert index.cues[1].text == "first"
    assert index.next_index(0) == 1
    assert index.previous_index(1) == 0


def test_previous_and_next_boundaries_clamp():
    index = CueIndex([_cue(1, 0, 1000), _cue(2, 1000, 2000)])
    assert index.previous_index(0) == 0
    assert index.next_index(1) == 1
    assert index.previous_index(None) == 0
    assert index.next_index(None) == 0


def test_empty_cue_list_navigation_returns_none():
    index = CueIndex([])
    assert index.active_cue_index(0) is None
    assert index.previous_index(0) is None
    assert index.next_index(0) is None
