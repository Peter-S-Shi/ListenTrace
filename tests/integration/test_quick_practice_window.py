from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtWidgets import QMessageBox

from listentrace.application.services import quick_practice_service as svc
from listentrace.application.services import recording_service
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db import recording_repository
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
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


def test_window_opens_with_transcript_hidden_at_listen_recall_step(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    session = svc.start_selected_session(conn, load_result.material.id, [load_result.cues[0].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")

    assert window._step == _STEP_LISTEN_RECALL
    assert "Cue 1 of 1" in window._progress_label.text()
    assert window._diagnosis_transcript_view.toPlainText() == ""
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
