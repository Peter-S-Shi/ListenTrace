from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtWidgets import QMessageBox

from listentrace.application.services import recording_service as svc
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
from listentrace.ui.widgets.recording_panel import RecordingPanel


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
    return material_id, get_cues_for_track(conn, track_row.id)


def _make_ready_recording(conn, recordings_dir, material_id, cue_id):
    recording, path = svc.begin_recording(conn, recordings_dir, material_id, cue_id, "dev", "Mic")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(struct.pack("<h", 0) * 8000)
    return svc.finish_recording(conn, recordings_dir, recording.id)


def test_deleting_a_take_in_one_panel_refreshes_a_second_open_panel_on_the_same_cue(
    qapp, conn, recordings_dir, monkeypatch
):
    """M12 Round 3/4 ghost-take fix: two windows (e.g. Shadowing Practice and a
    Guided Session Stage 4) can be open on the same cue at once. Deleting a take
    in one must not leave a stale, un-refreshable "Not Found" row in the other."""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    material_id, cues = _make_material_with_cues(conn)
    _make_ready_recording(conn, recordings_dir, material_id, cues[0].id)

    panel_a = RecordingPanel(conn, recordings_dir)
    panel_a.set_context(material_id, cues[0].id, None)
    panel_b = RecordingPanel(conn, recordings_dir)
    panel_b.set_context(material_id, cues[0].id, None)
    assert panel_a._takes_list.count() == 1
    assert panel_b._takes_list.count() == 1

    panel_b._takes_list.setCurrentRow(0)
    panel_b._on_delete_take_clicked()

    assert panel_b._takes_list.count() == 0
    assert panel_a._takes_list.count() == 0, (
        "panel_a's stale row must be cleared once panel_b deletes the same "
        "take -- this is the exact 'ghost take / Not Found' report from "
        "the first human QA pass"
    )
    panel_a.deleteLater()
    panel_b.deleteLater()


def test_sibling_panel_start_button_becomes_truthful_while_another_panel_is_recording(
    qapp, conn, recordings_dir, monkeypatch
):
    """M14 Corrective Batch A (A4): the domain/database invariant (migration
    8's partial unique index -- at most one `status = 'recording'` row across
    the whole app) already rejects a second simultaneous capture, but before
    this fix a sibling panel's Start Recording button stayed enabled and only
    failed the click. It must now reflect the true global state before the
    click, and must re-enable once the recording panel that started it stops
    (covering the abort/cancel path here specifically)."""
    from listentrace.infrastructure.media.recording import AudioInputDevice, RecordingController

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    fake_device = AudioInputDevice(device_id="dev-1", description="Fake Mic", is_default=True)
    monkeypatch.setattr(RecordingPanel, "_selected_device", lambda self: fake_device)
    monkeypatch.setattr(RecordingController, "set_device", lambda self, device_id: True)
    monkeypatch.setattr(RecordingController, "start", lambda self, path: None)

    material_id, cues = _make_material_with_cues(conn)

    panel_a = RecordingPanel(conn, recordings_dir)
    panel_a.set_context(material_id, cues[0].id, None)
    panel_b = RecordingPanel(conn, recordings_dir)
    panel_b.set_context(material_id, cues[1].id, None)

    assert panel_a._start_recording_button.isEnabled() is True
    assert panel_b._start_recording_button.isEnabled() is True

    panel_a._on_start_recording_clicked()
    assert panel_a._active_recording is not None
    assert panel_a._start_recording_button.isEnabled() is False  # its own capture

    assert panel_b._start_recording_button.isEnabled() is False, (
        "a sibling panel's Start Recording must become truthfully disabled "
        "once ANY panel begins recording, not just fail after the click"
    )
    assert "Another recording is in progress" in panel_b._recording_state_label.text()

    panel_a.abort_active_recording()

    assert panel_b._start_recording_button.isEnabled() is True, (
        "the sibling panel must re-enable once the recording that blocked it stops"
    )
    assert panel_b._recording_state_label.text() == ""

    panel_a.deleteLater()
    panel_b.deleteLater()


def _monkeypatch_fake_recording_hardware(monkeypatch):
    """Shared setup for the A4 acceptance-gap tests below: a fake device and
    a no-op `RecordingController` so `_on_start_recording_clicked()` runs the
    real production code path (real `begin_recording` DB write, real signal
    emission) without touching real audio hardware."""
    from listentrace.infrastructure.media.recording import AudioInputDevice, RecordingController

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    fake_device = AudioInputDevice(device_id="dev-1", description="Fake Mic", is_default=True)
    monkeypatch.setattr(RecordingPanel, "_selected_device", lambda self: fake_device)
    monkeypatch.setattr(RecordingController, "set_device", lambda self, device_id: True)
    monkeypatch.setattr(RecordingController, "start", lambda self, path: None)


def test_late_joining_panel_starts_disabled_when_a_recording_is_already_in_progress(
    qapp, conn, recordings_dir, monkeypatch
):
    """M14 Corrective Batch A4 acceptance gap: a `RecordingPanel` constructed
    and given a valid cue/device context *after* another panel already
    started recording must be truthfully disabled from the moment it gets a
    context -- not just once it happens to receive a `recording_started`
    event it was never alive to hear. This requires querying the
    authoritative DB state (`recording_service.has_active_recording`), not
    only historical event receipt."""
    _monkeypatch_fake_recording_hardware(monkeypatch)
    material_id, cues = _make_material_with_cues(conn)

    panel_a = RecordingPanel(conn, recordings_dir)
    panel_a.set_context(material_id, cues[0].id, None)
    panel_a._on_start_recording_clicked()
    assert panel_a._active_recording is not None

    # Panel B is constructed and given a context only now -- strictly after
    # A's `recording_started` signal already fired and had no listener.
    panel_b = RecordingPanel(conn, recordings_dir)
    panel_b.set_context(material_id, cues[1].id, None)

    assert panel_b._start_recording_button.isEnabled() is False, (
        "a panel that joins after recording already started must be "
        "truthfully disabled immediately, not stuck enabled because it "
        "missed the historical recording_started event"
    )
    assert "Another recording is in progress" in panel_b._recording_state_label.text()

    panel_a.abort_active_recording()
    assert panel_b._start_recording_button.isEnabled() is True, (
        "the late-joining panel must re-enable once the recording that "
        "blocked it stops"
    )

    panel_a.deleteLater()
    panel_b.deleteLater()


def test_immediate_startup_error_does_not_leave_sibling_panel_permanently_blocked(
    qapp, conn, recordings_dir, monkeypatch
):
    """M14 Corrective Batch A4 acceptance gap: if the recorder reports an
    error immediately around startup (e.g. the device vanished right after
    `begin_recording` created the DB row), reconciliation must be driven by
    authoritative current state, not by assuming perfect
    started-then-stopped signal ordering -- a sibling panel must not be left
    permanently blocked."""
    _monkeypatch_fake_recording_hardware(monkeypatch)
    material_id, cues = _make_material_with_cues(conn)

    panel_a = RecordingPanel(conn, recordings_dir)
    panel_a.set_context(material_id, cues[0].id, None)
    panel_b = RecordingPanel(conn, recordings_dir)
    panel_b.set_context(material_id, cues[1].id, None)

    panel_a._on_start_recording_clicked()
    assert panel_b._start_recording_button.isEnabled() is False

    # Simulate the recorder failing immediately after starting -- before any
    # further UI interaction settles.
    panel_a._on_recording_error("The selected microphone disappeared.")

    assert panel_a._active_recording is None
    assert panel_b._start_recording_button.isEnabled() is True, (
        "an immediate startup error must reconcile against authoritative "
        "state and release the sibling panel, not leave it permanently "
        "blocked by a recording that never actually completed"
    )
    assert panel_b._recording_state_label.text() == ""

    panel_a.deleteLater()
    panel_b.deleteLater()


def test_re_deleting_an_already_gone_take_clears_the_stale_row_without_raising(
    qapp, conn, recordings_dir, monkeypatch
):
    """The second half of the ghost-take fix: clicking Delete on a row whose
    underlying DB row is already gone (e.g. the cross-window signal above
    never reached this panel for some reason) must not silently swallow an
    uncaught `RecordingNotFoundError` and leave the row stuck forever."""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    material_id, cues = _make_material_with_cues(conn)
    recording = _make_ready_recording(conn, recordings_dir, material_id, cues[0].id)

    panel = RecordingPanel(conn, recordings_dir)
    panel.set_context(material_id, cues[0].id, None)
    assert panel._takes_list.count() == 1

    # Simulate "deleted elsewhere without notifying this panel" by removing the
    # DB row directly, bypassing the panel entirely.
    svc.delete_take(conn, recordings_dir, recording.id)

    panel._takes_list.setCurrentRow(0)
    panel._on_delete_take_clicked()  # must not raise RecordingNotFoundError

    assert panel._takes_list.count() == 0
    panel.deleteLater()
