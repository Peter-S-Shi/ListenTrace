from __future__ import annotations

from listentrace.domain.enums.recording_status import RecordingStatus
from listentrace.domain.services.recording_rules import (
    build_relative_recording_path,
    is_valid_recording_transition,
)


def test_recording_can_transition_to_ready():
    assert is_valid_recording_transition(RecordingStatus.RECORDING.value, RecordingStatus.READY.value)


def test_recording_can_transition_to_failed():
    assert is_valid_recording_transition(RecordingStatus.RECORDING.value, RecordingStatus.FAILED.value)


def test_ready_is_terminal():
    assert not is_valid_recording_transition(RecordingStatus.READY.value, RecordingStatus.FAILED.value)
    assert not is_valid_recording_transition(RecordingStatus.READY.value, RecordingStatus.RECORDING.value)


def test_failed_is_terminal():
    assert not is_valid_recording_transition(RecordingStatus.FAILED.value, RecordingStatus.READY.value)
    assert not is_valid_recording_transition(RecordingStatus.FAILED.value, RecordingStatus.RECORDING.value)


def test_recording_cannot_transition_to_itself():
    assert not is_valid_recording_transition(RecordingStatus.RECORDING.value, RecordingStatus.RECORDING.value)


def test_build_relative_recording_path_groups_by_material():
    path = build_relative_recording_path(42, "abc123.wav")
    assert path == "42/abc123.wav"


def test_build_relative_recording_path_never_embeds_content_beyond_the_given_filename():
    # The function only ever combines material_id with the caller-supplied
    # filename — no other field (title, transcript, etc.) sneaks in.
    path = build_relative_recording_path(1, "f.wav")
    assert path == "1/f.wav"
