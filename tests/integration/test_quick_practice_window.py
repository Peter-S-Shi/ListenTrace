from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtWidgets import QMessageBox

from listentrace.application.services import loop_grace_service
from listentrace.application.services import quick_practice_service as svc
from listentrace.application.services import recording_service
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db import recording_repository
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog
from listentrace.ui.windows.quick_practice_window import (
    _STEP_DIAGNOSE,
    _STEP_LISTEN_RECALL,
    _STEP_REPLAY,
    _STEP_SUMMARY,
    QuickPracticeWindow,
)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "quick_practice_window.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _import_material(conn, tmp_path, cue_texts=("Bonjour tout le monde", "Comment ca va", "Au revoir")):
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    lines = []
    for i, text in enumerate(cue_texts):
        start_s, end_s = i, i + 1
        lines.append(
            f"{i + 1}\n00:00:0{start_s},000 --> 00:00:0{end_s},000\n{text}\n"
        )
    srt.write_text("\n".join(lines), encoding="utf-8")
    result = import_material(conn, media_path, srt, "QP Lesson")
    return load_material_for_player(conn, result.material_id)


def _open_window(conn, tmp_path, cue_ids, recordings_dir=None):
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, cue_ids or [c.id for c in load_result.cues[:2]])
    window = QuickPracticeWindow(conn, load_result, session.id, recordings_dir or (tmp_path / "recordings"))
    return window, load_result, session.id


def test_loop_settings_button_opens_the_shared_dialog_from_either_step(qapp, conn, tmp_path):
    window, load_result, _ = _open_window(conn, tmp_path, None)

    window._on_open_loop_settings()
    assert isinstance(window._loop_settings_dialog, MaterialLoopSettingsDialog)
    first = window._loop_settings_dialog
    window._listen_loop_settings_button.click()
    window._replay_loop_settings_button.click()
    assert window._loop_settings_dialog is first
    window.close()


def test_material_override_changed_updates_this_windows_live_session_grace(qapp, conn, tmp_path):
    window, load_result, _ = _open_window(conn, tmp_path, None)
    material_id = load_result.material.id

    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    loop_grace_change_bus.material_override_changed.emit(material_id)

    assert window._player_session._loop_end_grace_ms == 90
    window.close()


def test_window_opens_with_transcript_hidden_at_listen_recall_step(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")

    assert window._step == _STEP_LISTEN_RECALL
    assert "Cue 1 of 1" in window._progress_label.text()
    assert window._diagnosis_transcript_view.toPlainText() == ""
    window.close()


def test_play_button_is_cue_scoped_not_whole_media(qapp, conn, tmp_path):
    """M12 Round 1 Playback Contract (P1): Play in the Listen step must stop
    at the current cue's end, not drift into the next cue's audio."""
    from PySide6.QtCore import QEventLoop, QTimer

    def _pump(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path, seconds=4)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nBonjour\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nComment ca va\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nAu revoir\n",
        encoding="utf-8",
    )
    result = import_material(conn, media_path, srt, "QP Lesson")
    load_result = load_material_for_player(conn, result.material_id)
    cue = load_result.cues[1]  # 1000-2000ms, so a "just play from 0" bug would overshoot it
    session = svc.start_selected_session(conn, load_result.material.id, [cue.id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")
    _pump(500)  # let the async media load finish before seeking away from position 0

    window._on_play_clicked()
    _pump((cue.end_ms - cue.start_ms) + 500)

    assert window._playback.is_playing is False, (
        "Play must stop at this cue's end, not continue playing into the next cue"
    )
    assert window._playback.position_ms < cue.end_ms + 200
    window.close()


def test_step_action_disabled_until_a_recall_result_is_chosen(qapp, conn, tmp_path):
    window, _, _ = _open_window(conn, tmp_path, None)
    assert not window._step_action_button.isEnabled()
    window._recall_radio_buttons["understood"].setChecked(True)
    assert window._step_action_button.isEnabled()
    window.close()


def test_recall_continue_reveals_transcript_and_advances_to_diagnose(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")

    window._recall_radio_buttons["missed"].setChecked(True)
    window._on_step_action_clicked()

    assert window._step == _STEP_DIAGNOSE
    assert window._diagnosis_transcript_view.toPlainText() == load_result.cues[0].text
    item = svc.load_session_state(conn, session.id).items[0].item
    assert item.recall_result == "missed"
    assert item.transcript_revealed is True
    window.close()


def test_full_two_cue_run_reaches_summary(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    cue_ids = [load_result.cues[0].id, load_result.cues[2].id]
    session = svc.start_selected_session(conn, load_result.material.id, cue_ids)
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")

    window._recall_radio_buttons["missed"].setChecked(True)
    window._heard_fragment_edit.setText("bonjoor")
    window._on_step_action_clicked()
    assert window._step == _STEP_DIAGNOSE
    assert window._diagnosis_transcript_view.toPlainText() == load_result.cues[0].text

    window._diagnosis_label_checkboxes["misheard"].setChecked(True)
    window._diagnosis_heard_as_edit.setText("bonjoor")
    window._on_save_diagnosis_clicked()
    assert window._diagnosis_list.count() == 1

    window._on_step_action_clicked()  # -> replay
    assert window._step == _STEP_REPLAY
    assert window._step_action_button.text() == "Next Cue"

    window._on_mark_shadowed_clicked()
    assert window._current_item_state().item.shadowed_at is not None

    window._on_step_action_clicked()  # -> item 2
    assert window._index == 1
    assert window._step == _STEP_LISTEN_RECALL
    assert "Cue 2 of 2" in window._progress_label.text()

    window._recall_radio_buttons["understood"].setChecked(True)
    window._on_step_action_clicked()  # reveal
    window._on_step_action_clicked()  # -> replay
    assert window._step_action_button.text() == "Finish Run"
    window._on_step_action_clicked()  # -> complete session

    assert window._step == _STEP_SUMMARY
    session_after = svc.get_session(conn, session.id)
    assert session_after.status == "completed"
    assert "Cues completed: 2" in window._summary_label.text()
    window.close()


def test_delete_diagnosis_prompts_for_confirmation(qapp, conn, tmp_path, monkeypatch):
    """M12.3 regression: deleting a Quick Practice diagnosis must be confirmed like
    every other destructive action in the app (GuidedSessionWindow's equivalent
    already does; this window previously deleted with no prompt at all)."""
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")

    window._recall_radio_buttons["missed"].setChecked(True)
    window._on_step_action_clicked()  # -> reveal & diagnose
    window._diagnosis_label_checkboxes["misheard"].setChecked(True)
    window._diagnosis_heard_as_edit.setText("bonjoor")
    window._on_save_diagnosis_clicked()
    assert window._diagnosis_list.count() == 1
    window._diagnosis_list.setCurrentRow(0)
    assert window._editing_diagnosis_id is not None

    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: (asked.append(True), QMessageBox.StandardButton.No)[1])
    window._on_delete_diagnosis_clicked()
    assert asked  # a confirmation prompt was actually shown
    assert len(svc.list_item_diagnosis(conn, window._current_item_state().item.id)) == 1  # cancel kept it

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._on_delete_diagnosis_clicked()
    assert svc.list_item_diagnosis(conn, window._current_item_state().item.id) == []
    window.close()


def test_zero_progress_close_discards_without_prompting(qapp, conn, tmp_path, monkeypatch):
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")

    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(True))
    window.close()

    assert not asked  # no confirmation needed — nothing to lose
    assert svc.get_session(conn, session.id) is None


def test_close_with_progress_prompts_and_abandons_on_confirm(qapp, conn, tmp_path, monkeypatch):
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id, load_result.cues[1].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")
    window._recall_radio_buttons["understood"].setChecked(True)
    window._on_step_action_clicked()  # reveal
    window._on_step_action_clicked()  # -> replay
    window._on_step_action_clicked()  # -> complete item 1, advance to item 2

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.close()

    session_after = svc.get_session(conn, session.id)
    assert session_after.status == "abandoned"


def test_close_cancelled_does_not_touch_active_recording_take_playback_or_session(qapp, conn, tmp_path, monkeypatch):
    """Acceptance correction: closeEvent must decide-then-act — nothing
    about the active recording, take playback, source playback, or Quick
    Practice session may be mutated until after the learner has confirmed.
    Cancelling the close prompt must leave an in-progress recording
    untouched and the session `active`."""
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id, load_result.cues[1].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")
    window._recall_radio_buttons["understood"].setChecked(True)
    window._on_step_action_clicked()  # reveal
    window._on_step_action_clicked()  # -> replay
    window._on_step_action_clicked()  # -> complete item 1, advance to item 2

    recording, _absolute_path = recording_service.begin_recording(
        conn, tmp_path / "recordings", load_result.material.id, load_result.cues[1].id, "fake-device", "Fake Mic"
    )
    window._recording_panel._active_recording = recording

    abort_calls = []
    monkeypatch.setattr(window._recording_panel, "abort_active_recording", lambda: abort_calls.append(True))
    release_calls = []
    monkeypatch.setattr(window._recording_panel, "release_take_playback", lambda: release_calls.append(True))
    stop_calls = []
    monkeypatch.setattr(window._playback, "stop", lambda: stop_calls.append(True))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    accepted = window.close()

    assert accepted is False
    assert abort_calls == []
    assert release_calls == []
    assert stop_calls == []
    assert svc.get_session(conn, session.id).status == "active"
    still_recording = recording_repository.get_recording(conn, recording.id)
    assert still_recording.status == "recording"  # never aborted/failed by the cancelled close


def test_close_with_progress_cancelled_keeps_the_window_open(qapp, conn, tmp_path, monkeypatch):
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id, load_result.cues[1].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")
    window._recall_radio_buttons["understood"].setChecked(True)
    window._on_step_action_clicked()
    window._on_step_action_clicked()
    window._on_step_action_clicked()

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    accepted = window.close()

    assert accepted is False
    assert svc.get_session(conn, session.id).status == "active"
    window.close()  # cleanup: discard/abandon via a real close for the next test run


def test_normal_close_really_aborts_an_in_progress_recording_and_survives_reopening(qapp, tmp_path):
    """Post-M10 Phase B shutdown audit: every prior close-behavior test
    mocks `abort_active_recording` itself to prove the *ordering* fix (the
    Milestone 10 correction) -- none of them let the real
    `recording_service.fail_recording` path actually run end-to-end during a
    normal window close, and none of them re-open a fresh connection
    afterward to prove the result was actually durable, not just correct in
    the same still-open connection. This test does both: a real in-progress
    recording row is really aborted (not spied on) by a normal close, and a
    brand-new connection to the same database file (simulating the next
    application launch) reads back the exact same failed status."""
    db_path = tmp_path / "shutdown_audit.db"
    conn = open_connection(db_path)
    migrate(conn)
    recordings_dir = tmp_path / "recordings"

    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id])
    window = QuickPracticeWindow(conn, load_result, session.id, recordings_dir)

    recording, absolute_path = recording_service.begin_recording(
        conn, recordings_dir, load_result.material.id, load_result.cues[0].id, "fake-device", "Fake Mic"
    )
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(b"partial-capture")
    window._recording_panel._active_recording = recording

    accepted = window.close()  # zero completed items -> silent discard, no confirmation prompt

    assert accepted is True
    assert svc.get_session(conn, session.id) is None  # session discarded, exactly as a normal close should
    aborted = recording_repository.get_recording(conn, recording.id)
    assert aborted.status == "failed"  # the real abort path ran, not a mock
    assert not absolute_path.exists()  # the partial capture file was really cleaned up

    conn.close()  # simulates normal application shutdown -- no explicit flush needed beyond this

    # Simulate the next application launch: an entirely fresh connection to
    # the same database file must see exactly what the closed session left.
    reopened = open_connection(db_path)
    reread = recording_repository.get_recording(reopened, recording.id)
    assert reread.status == "failed"

    # A normal close must not leave anything for startup crash-recovery to
    # find -- the close path itself already resolved the recording (failed)
    # and the session (discarded). If either recovery function found
    # something here, it would mean the close path left a dangling
    # 'recording'/'active' row for the *next launch* to clean up instead,
    # which is exactly what a genuine shutdown defect would look like.
    assert recording_service.recover_interrupted_recordings(reopened, recordings_dir) == 0
    assert svc.recover_interrupted_sessions(reopened) == 0
    reopened.close()
