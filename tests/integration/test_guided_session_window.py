from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox

from listentrace.application.services import practice_session_service as svc
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "guided.db")
    migrate(connection)
    yield connection
    connection.close()


def _run_event_loop(app, timeout_ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _open_guided_window(conn, tmp_path, media_path=None):
    if media_path is None:
        media_path = tmp_path / "lesson.wav"
        _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nBonjour tout le monde\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nSecond cue\n",
        encoding="utf-8",
    )
    result = import_material(conn, media_path, srt, "Guided Lesson")
    load_result = load_material_for_player(conn, result.material_id)
    session = svc.start_session(conn, result.material_id)
    window = GuidedSessionWindow(conn, load_result, session.id, tmp_path / "recordings")
    return window, result.material_id, session.id


def test_guided_session_starts_at_stage1_with_transcript_hidden(qapp, conn, tmp_path, monkeypatch):
    window, _, _ = _open_guided_window(conn, tmp_path)
    assert window._stack.currentIndex() == 0
    assert "Stage 1 of 5" in window._stage_progress_label.text()
    # Stage 3's cue list/transcript must not be pre-populated while hidden.
    assert window._diagnosis_cue_list.count() == 0
    window.close()


def test_stage_progress_label_updates_on_navigation(qapp, conn, tmp_path, monkeypatch):
    window, _, _ = _open_guided_window(conn, tmp_path)
    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()
    assert "Stage 2 of 5" in window._stage_progress_label.text()
    window.close()


def test_transcript_reveal_requires_confirmation_and_locks_stage1_2(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    window, _, session_id = _open_guided_window(conn, tmp_path)
    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage 2
    window._on_skip_stage_clicked()  # -> stage 3, triggers reveal confirmation (auto-Yes)

    assert window._current_stage == "transcript_diagnosis"
    session = svc.get_session(conn, session_id)
    assert session.transcript_revealed_at is not None
    assert window._diagnosis_cue_list.count() == 2

    # Stage 1 is now read-only.
    assert window._stage1_edits["where"].isReadOnly() is True
    window.close()


def test_reveal_confirmation_declined_stays_on_stage2(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    window, _, session_id = _open_guided_window(conn, tmp_path)
    window._on_save_and_continue_clicked()  # -> stage 2
    window._on_save_and_continue_clicked()  # attempts -> stage 3, declined

    assert window._current_stage == "keyword_capture"
    assert svc.get_session(conn, session_id).transcript_revealed_at is None
    window.close()


def test_close_and_resume_restores_stage_and_responses(qapp, conn, tmp_path):
    window, material_id, session_id = _open_guided_window(conn, tmp_path)
    window._stage1_edits["who_is_speaking"].setPlainText("A man")
    window._on_save_and_continue_clicked()  # -> stage 2, persists stage1 text
    window.close()

    load_result = load_material_for_player(conn, material_id)
    reopened = GuidedSessionWindow(conn, load_result, session_id, tmp_path / "recordings")
    assert reopened._stack.currentIndex() == 1
    assert "Stage 2 of 5" in reopened._stage_progress_label.text()
    assert reopened._stage1_edits["who_is_speaking"].toPlainText() == "A man"
    reopened.close()


def test_m4_annotation_semantics_reused_misheard_requires_heard_as(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window, _, session_id = _open_guided_window(conn, tmp_path)
    window._show_stage("transcript_diagnosis")
    window._diagnosis_cue_list.setCurrentRow(0)

    window._diagnosis_label_checkboxes["misheard"].setChecked(True)
    window._on_save_diagnosis_clicked()
    assert "heard_as" in window._status_label.text() or window._diagnosis_list.count() == 0

    window._diagnosis_heard_as_edit.setText("Bonjoor")
    window._on_save_diagnosis_clicked()
    assert window._diagnosis_list.count() == 1
    badge_color = window._diagnosis_list.item(0).icon().pixmap(12, 12).toImage().pixelColor(0, 0)
    from listentrace.application.services import label_preference_service

    expected = label_preference_service.get_label_preferences(conn)["misheard"]
    assert badge_color.name() == QColor(expected).name()
    window.close()


def test_invalid_media_preserves_session_text_workflow(qapp, conn, tmp_path):
    bad_path = tmp_path / "bad.mp3"
    bad_path.write_bytes(b"not a real mp3 file, just garbage bytes" * 20)

    window, _, session_id = _open_guided_window(conn, tmp_path, media_path=bad_path)
    _run_event_loop(qapp, 2000)

    assert window._playback_usable is False
    assert "Playback error" in window._status_label.text()

    # Text-based stage navigation must remain fully usable despite the playback error.
    window._stage1_edits["result"].setPlainText("They agree to meet again.")
    window._on_save_and_continue_clicked()
    state = svc.load_session_state(conn, session_id)
    assert state.stage_responses["global_comprehension"]["result"] == "They agree to meet again."
    assert state.stage_progress["global_comprehension"].status == "completed"
    window.close()


def test_completed_session_reopens_read_only(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    window, material_id, session_id = _open_guided_window(conn, tmp_path)
    for stage_key in ("global_comprehension", "keyword_capture", "transcript_diagnosis", "shadowing", "final_summary"):
        window._show_stage(stage_key)
        window._on_skip_stage_clicked() if stage_key != window._current_stage else None
    # Ensure every stage actually resolved (skip whichever remain not_started).
    state = svc.load_session_state(conn, session_id)
    for stage_key, progress in state.stage_progress.items():
        if progress.status not in ("completed", "skipped"):
            svc.skip_stage(conn, session_id, stage_key)
    svc.complete_session(conn, session_id)
    window.close()

    load_result = load_material_for_player(conn, material_id)
    reopened = GuidedSessionWindow(conn, load_result, session_id, tmp_path / "recordings")
    assert "COMPLETED" in reopened._stage_progress_label.text()
    assert reopened._continue_button.isEnabled() is False
    assert reopened._skip_button.isEnabled() is False
    assert reopened._abandon_button.isEnabled() is False
    reopened.close()


def test_unsaved_capture_draft_survives_unrelated_stage3_refresh(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window, _, session_id = _open_guided_window(conn, tmp_path)
    window._on_save_and_continue_clicked()  # -> stage2

    # Draft an unsaved capture (not yet added) then navigate away and back.
    window._capture_text_edit.setText("draft fragment")
    # A same-stage refresh (as triggered elsewhere by _refresh_state after a
    # save) must not wipe an unsaved draft still sitting in the input field.
    window._refresh_state()
    assert window._capture_text_edit.text() == "draft fragment"
    window.close()
