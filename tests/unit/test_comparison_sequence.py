from __future__ import annotations

from listentrace.domain.services.comparison_sequence import ComparisonSequencer, ComparisonStep


def test_initial_state_is_done_and_not_active():
    sequencer = ComparisonSequencer()
    assert sequencer.step is ComparisonStep.DONE
    assert not sequencer.is_active


def test_full_sequence_progresses_through_every_step():
    sequencer = ComparisonSequencer()
    assert sequencer.start() is ComparisonStep.PLAY_SOURCE
    assert sequencer.is_active
    assert sequencer.on_source_finished() is ComparisonStep.WAIT
    assert sequencer.on_pause_elapsed() is ComparisonStep.PLAY_RECORDING
    assert sequencer.on_recording_finished() is ComparisonStep.DONE
    assert not sequencer.is_active


def test_out_of_order_events_are_ignored():
    sequencer = ComparisonSequencer()
    sequencer.start()
    # Calling on_pause_elapsed before on_source_finished must not skip a step.
    assert sequencer.on_pause_elapsed() is ComparisonStep.PLAY_SOURCE
    assert sequencer.on_recording_finished() is ComparisonStep.PLAY_SOURCE


def test_events_while_done_are_no_ops():
    sequencer = ComparisonSequencer()
    assert sequencer.on_source_finished() is ComparisonStep.DONE
    assert sequencer.on_pause_elapsed() is ComparisonStep.DONE
    assert sequencer.on_recording_finished() is ComparisonStep.DONE


def test_cancel_returns_to_done_from_any_step():
    sequencer = ComparisonSequencer()
    sequencer.start()
    sequencer.on_source_finished()
    assert sequencer.cancel() is ComparisonStep.DONE
    assert not sequencer.is_active


def test_starting_again_after_done_works():
    sequencer = ComparisonSequencer()
    sequencer.start()
    sequencer.on_source_finished()
    sequencer.on_pause_elapsed()
    sequencer.on_recording_finished()
    assert sequencer.start() is ComparisonStep.PLAY_SOURCE
