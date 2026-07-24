from __future__ import annotations

import struct
import wave

import pytest

from listentrace.application.errors import RecordingNotFoundError, RecordingValidationError
from listentrace.application.services import practice_session_service as session_svc
from listentrace.application.services import recording_service as svc
from listentrace.domain.enums.recording_status import RecordingStatus
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_subtitle_track_for_material,
    insert_material,
    insert_subtitle_track,
)
from listentrace.infrastructure.media.recording import AudioInputDevice

_DEVICE_A = AudioInputDevice(device_id="aaa", description="Mic A", is_default=True)
_DEVICE_B = AudioInputDevice(device_id="bbb", description="Mic B", is_default=False)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def recordings_dir(tmp_path):
    return tmp_path / "recordings"


def _make_material_with_cues(conn, cue_texts=("Bonjour", "Comment ca va")):
    material_id = insert_material(conn, Material(title="Lesson", media_path="C:/media/lesson.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/lesson.srt",
        cues=[
            SubtitleCue(cue_index=i + 1, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=text)
            for i, text in enumerate(cue_texts)
        ],
    )
    insert_subtitle_track(conn, track)
    track_row = get_subtitle_track_for_material(conn, material_id)
    cues = get_cues_for_track(conn, track_row.id)
    return material_id, cues


def _write_valid_wav(path, seconds=1, framerate=8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _write_empty_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


# ---- begin_recording: ownership + single-active-recording ----


def test_begin_recording_creates_a_recording_row_in_recording_status(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    assert recording.id is not None
    assert recording.status == RecordingStatus.RECORDING.value
    assert recording.material_id == material_id
    assert recording.subtitle_cue_id == cues[0].id
    assert recording.practice_session_id is None
    assert path == recordings_dir / recording.relative_file_path
    assert path.suffix == ".wav"


def test_begin_recording_rejects_cue_material_mismatch(conn, recordings_dir):
    material_a, cues_a = _make_material_with_cues(conn)
    material_b, _ = _make_material_with_cues(conn, cue_texts=("Different",))
    with pytest.raises(RecordingValidationError) as exc_info:
        svc.begin_recording(conn, recordings_dir, material_b, cues_a[0].id, _DEVICE_A.device_id, _DEVICE_A.description)
    assert exc_info.value.category == "cue_material_mismatch"


def test_begin_recording_rejects_a_session_from_a_different_material(conn, recordings_dir):
    material_a, cues_a = _make_material_with_cues(conn)
    material_b, _ = _make_material_with_cues(conn, cue_texts=("Different",))
    session_b = session_svc.start_session(conn, material_b)
    with pytest.raises(RecordingValidationError) as exc_info:
        svc.begin_recording(
            conn, recordings_dir, material_a, cues_a[0].id, _DEVICE_A.device_id, _DEVICE_A.description,
            practice_session_id=session_b.id,
        )
    assert exc_info.value.category == "session_material_mismatch"


def test_begin_recording_accepts_a_session_belonging_to_the_material(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    session = session_svc.start_session(conn, material_id)
    recording, _ = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description,
        practice_session_id=session.id,
    )
    assert recording.practice_session_id == session.id


def test_begin_recording_refuses_a_second_concurrent_recording(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    svc.begin_recording(conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description)
    with pytest.raises(RecordingValidationError) as exc_info:
        svc.begin_recording(conn, recordings_dir, material_id, cues[1].id, _DEVICE_A.device_id, _DEVICE_A.description)
    assert exc_info.value.category == "recording_in_progress"


# ---- finish_recording / fail_recording ----


def test_finish_recording_marks_ready_with_duration_for_a_valid_wav(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_valid_wav(path, seconds=2, framerate=8000)

    updated = svc.finish_recording(conn, recordings_dir, recording.id)

    assert updated.status == RecordingStatus.READY.value
    assert updated.duration_ms == 2000
    assert path.exists()


def test_finish_recording_marks_failed_for_an_empty_file(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_empty_file(path)

    updated = svc.finish_recording(conn, recordings_dir, recording.id)

    assert updated.status == RecordingStatus.FAILED.value
    assert updated.failure_detail
    assert not path.exists()  # the invalid file is cleaned up, not kept as a "playable" take


def test_finish_recording_marks_failed_for_a_missing_file(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    # Never actually written — simulates a capture that never produced a file.
    updated = svc.finish_recording(conn, recordings_dir, recording.id)
    assert updated.status == RecordingStatus.FAILED.value


def test_finish_recording_requires_in_progress_status(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_valid_wav(path)
    svc.finish_recording(conn, recordings_dir, recording.id)

    with pytest.raises(RecordingValidationError) as exc_info:
        svc.finish_recording(conn, recordings_dir, recording.id)
    assert exc_info.value.category == "invalid_transition"


def test_fail_recording_marks_failed_and_deletes_partial_file(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_valid_wav(path)

    updated = svc.fail_recording(conn, recordings_dir, recording.id, "Microphone disconnected mid-capture.")

    assert updated.status == RecordingStatus.FAILED.value
    assert updated.failure_detail == "Microphone disconnected mid-capture."
    assert not path.exists()


def test_fail_recording_requires_in_progress_status(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_valid_wav(path)
    svc.finish_recording(conn, recordings_dir, recording.id)

    with pytest.raises(RecordingValidationError):
        svc.fail_recording(conn, recordings_dir, recording.id, "too late")


# ---- listing ----


def test_list_takes_for_cue_orders_by_creation(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    ids = []
    for _ in range(3):
        recording, path = svc.begin_recording(
            conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
        )
        _write_valid_wav(path)
        svc.finish_recording(conn, recordings_dir, recording.id)
        ids.append(recording.id)

    takes = svc.list_takes_for_cue(conn, cues[0].id)
    assert [t.id for t in takes] == ids
    # New takes never overwrite older takes.
    assert len({t.relative_file_path for t in takes}) == 3


def test_list_takes_for_material_includes_all_cues(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    for cue in cues:
        recording, path = svc.begin_recording(
            conn, recordings_dir, material_id, cue.id, _DEVICE_A.device_id, _DEVICE_A.description
        )
        _write_valid_wav(path)
        svc.finish_recording(conn, recordings_dir, recording.id)

    takes = svc.list_takes_for_material(conn, material_id)
    assert {t.subtitle_cue_id for t in takes} == {cue.id for cue in cues}


# ---- deletion ----


def test_delete_take_removes_row_and_file(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_valid_wav(path)
    svc.finish_recording(conn, recordings_dir, recording.id)

    svc.delete_take(conn, recordings_dir, recording.id)

    assert not path.exists()
    assert svc.get_take(conn, recording.id) is None


def test_delete_take_raises_not_found_for_unknown_id(conn, recordings_dir):
    with pytest.raises(RecordingNotFoundError):
        svc.delete_take(conn, recordings_dir, 999999)


def test_delete_take_refuses_to_delete_an_in_progress_recording(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    with pytest.raises(RecordingValidationError) as exc_info:
        svc.delete_take(conn, recordings_dir, recording.id)
    assert exc_info.value.category == "recording_in_progress"


def test_delete_take_leaves_row_intact_if_file_deletion_fails(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    # Force unlink() to fail: put a *directory* where the managed file should be.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()
    svc.finish_recording(conn, recordings_dir, recording.id)  # invalid capture -> failed, but path is a dir so...
    # finish_recording's own best-effort delete also can't remove a directory;
    # the row is 'failed' either way. Re-fetch to confirm the row still exists
    # and then verify delete_take surfaces the failure rather than reporting success.
    stored = svc.get_take(conn, recording.id)
    assert stored is not None
    assert stored.status == RecordingStatus.FAILED.value
    with pytest.raises(RecordingValidationError) as exc_info:
        svc.delete_take(conn, recordings_dir, recording.id)
    assert exc_info.value.category == "file_deletion_failed"
    # The database row must still exist — never falsely reported as deleted.
    assert svc.get_take(conn, recording.id) is not None


def test_delete_takes_for_cue_deletes_all_takes(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    for _ in range(2):
        recording, path = svc.begin_recording(
            conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
        )
        _write_valid_wav(path)
        svc.finish_recording(conn, recordings_dir, recording.id)

    summary = svc.delete_takes_for_cue(conn, recordings_dir, cues[0].id)

    assert summary.all_succeeded
    assert len(summary.deleted_ids) == 2
    assert svc.list_takes_for_cue(conn, cues[0].id) == []


def test_delete_takes_for_material_deletes_across_multiple_cues(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    for cue in cues:
        recording, path = svc.begin_recording(
            conn, recordings_dir, material_id, cue.id, _DEVICE_A.device_id, _DEVICE_A.description
        )
        _write_valid_wav(path)
        svc.finish_recording(conn, recordings_dir, recording.id)

    summary = svc.delete_takes_for_material(conn, recordings_dir, material_id)

    assert summary.all_succeeded
    assert len(summary.deleted_ids) == len(cues)
    assert svc.list_takes_for_material(conn, material_id) == []


def test_delete_takes_for_material_does_not_touch_a_different_materials_recordings(conn, recordings_dir):
    material_a, cues_a = _make_material_with_cues(conn)
    material_b, cues_b = _make_material_with_cues(conn, cue_texts=("Other",))
    for material_id, cue in ((material_a, cues_a[0]), (material_b, cues_b[0])):
        recording, path = svc.begin_recording(
            conn, recordings_dir, material_id, cue.id, _DEVICE_A.device_id, _DEVICE_A.description
        )
        _write_valid_wav(path)
        svc.finish_recording(conn, recordings_dir, recording.id)

    svc.delete_takes_for_material(conn, recordings_dir, material_a)

    assert svc.list_takes_for_material(conn, material_a) == []
    assert len(svc.list_takes_for_material(conn, material_b)) == 1


# ---- startup recovery sweep ----


def test_recover_interrupted_recordings_marks_stale_rows_failed_and_cleans_files(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_valid_wav(path)  # left mid-capture, e.g. by a crash — never finish_recording'd

    recovered_count = svc.recover_interrupted_recordings(conn, recordings_dir)

    assert recovered_count == 1
    updated = svc.get_take(conn, recording.id)
    assert updated is not None
    assert updated.status == RecordingStatus.FAILED.value
    assert not path.exists()


def test_recover_interrupted_recordings_returns_zero_when_nothing_stale(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    _write_valid_wav(path)
    svc.finish_recording(conn, recordings_dir, recording.id)

    assert svc.recover_interrupted_recordings(conn, recordings_dir) == 0


def test_recovery_allows_a_new_recording_after_clearing_a_stuck_row(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    svc.begin_recording(conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description)
    svc.recover_interrupted_recordings(conn, recordings_dir)

    # The single-active-recording guard must no longer see the stale row.
    recording, _ = svc.begin_recording(
        conn, recordings_dir, material_id, cues[1].id, _DEVICE_A.device_id, _DEVICE_A.description
    )
    assert recording.status == RecordingStatus.RECORDING.value


# ---- device resolution ----


def test_resolve_preferred_device_returns_default_when_no_preference_saved(conn, monkeypatch):
    monkeypatch.setattr(svc, "list_audio_input_devices", lambda: [_DEVICE_B, _DEVICE_A])
    resolution = svc.resolve_preferred_device(conn)
    assert resolution.device == _DEVICE_A  # is_default=True
    assert resolution.fallback_reason is None


def test_resolve_preferred_device_with_no_devices_at_all(conn, monkeypatch):
    monkeypatch.setattr(svc, "list_audio_input_devices", lambda: [])
    resolution = svc.resolve_preferred_device(conn)
    assert resolution.device is None
    assert resolution.fallback_reason


def test_resolve_preferred_device_returns_saved_device_when_still_available(conn, monkeypatch):
    monkeypatch.setattr(svc, "list_audio_input_devices", lambda: [_DEVICE_A, _DEVICE_B])
    svc.remember_device_choice(conn, _DEVICE_B.device_id, _DEVICE_B.description)
    resolution = svc.resolve_preferred_device(conn)
    assert resolution.device == _DEVICE_B
    assert resolution.fallback_reason is None


def test_resolve_preferred_device_does_not_silently_substitute_when_saved_device_missing(conn, monkeypatch):
    monkeypatch.setattr(svc, "list_audio_input_devices", lambda: [_DEVICE_A, _DEVICE_B])
    svc.remember_device_choice(conn, "vanished-device-id", "Old Headset")
    resolution = svc.resolve_preferred_device(conn)
    # Must not silently fall back to _DEVICE_A or _DEVICE_B — the learner must
    # be told and choose explicitly.
    assert resolution.device is None
    assert "no longer available" in resolution.fallback_reason


def test_remember_device_choice_persists_and_upserts(conn):
    svc.remember_device_choice(conn, "id-1", "First Mic")
    svc.remember_device_choice(conn, "id-2", "Second Mic")
    from listentrace.infrastructure.db.recording_repository import get_microphone_preference

    stored = get_microphone_preference(conn)
    assert stored.device_id == "id-2"
    assert stored.device_description == "Second Mic"


# ---- Stage 4 non-interference (Guided Session integration) ----


def test_recording_lifecycle_does_not_alter_shadowing_or_session_completion_state(conn, recordings_dir):
    material_id, cues = _make_material_with_cues(conn)
    session = session_svc.start_session(conn, material_id)
    session_svc.enter_stage(conn, session.id, "shadowing")

    state_before = session_svc.load_session_state(conn, session.id)
    progress_before = {p.subtitle_cue_id: (p.status, p.practice_count) for p in state_before.shadowing_progress}
    stage_status_before = state_before.stage_progress["shadowing"].status

    recording, path = svc.begin_recording(
        conn, recordings_dir, material_id, cues[0].id, _DEVICE_A.device_id, _DEVICE_A.description,
        practice_session_id=session.id,
    )
    _write_valid_wav(path)
    svc.finish_recording(conn, recordings_dir, recording.id)
    svc.delete_take(conn, recordings_dir, recording.id)

    state_after = session_svc.load_session_state(conn, session.id)
    progress_after = {p.subtitle_cue_id: (p.status, p.practice_count) for p in state_after.shadowing_progress}
    assert progress_after == progress_before
    assert state_after.stage_progress["shadowing"].status == stage_status_before
