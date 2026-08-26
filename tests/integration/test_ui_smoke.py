from __future__ import annotations

import struct
import wave

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QInputDialog, QMessageBox

from listentrace.application.services import material_library_service as library
from listentrace.application.services import practice_session_service as session_service
from listentrace.application.services import quiz_service
from listentrace.application.services.material_import_service import import_material
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.main_window import MainWindow

_MULTI_CUE_SRT = (
    "1\n00:00:00,000 --> 00:00:02,000\nBonjour tout le monde\n\n"
    "2\n00:00:02,000 --> 00:00:04,000\nComment allez vous aujourd hui\n\n"
    "3\n00:00:04,000 --> 00:00:06,000\nJe suis tres content de vous voir\n\n"
    "4\n00:00:06,000 --> 00:00:08,000\nAu revoir et bonne journee\n\n"
    "5\n00:00:08,000 --> 00:00:10,000\nMerci beaucoup pour votre aide\n"
)


def _pump(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _make_wav(path, seconds=1, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def test_main_window_starts_with_initialized_database(qapp, tmp_path):
    db_path = tmp_path / "smoke.db"
    connection = open_connection(db_path)
    migrate(connection)

    window = MainWindow(connection, db_path, tmp_path / "recordings")

    assert window.windowTitle() == "ListenTrace"
    assert "Schema version: 12" in window._status_label.text()

    window.close()


def test_main_window_playback_settings_button_opens_the_global_dialog(qapp, tmp_path):
    from listentrace.ui.windows.playback_settings_dialog import PlaybackSettingsDialog

    db_path = tmp_path / "smoke.db"
    connection = open_connection(db_path)
    migrate(connection)
    window = MainWindow(connection, db_path, tmp_path / "recordings")

    window._on_open_playback_settings()

    assert isinstance(window._playback_settings_dialog, PlaybackSettingsDialog)
    first = window._playback_settings_dialog
    window._on_open_playback_settings()
    assert window._playback_settings_dialog is first, "reuses the same dialog instance"
    window.close()


def test_main_window_shows_empty_library_state(qapp, tmp_path):
    connection = open_connection(tmp_path / "empty.db")
    migrate(connection)

    window = MainWindow(connection, tmp_path / "empty.db", tmp_path / "recordings")

    assert window._material_list.count() == 1
    assert "empty" in window._material_list.item(0).text().lower()

    window.close()


def test_main_window_lists_imported_material_and_shows_detail(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.mp3"
    media.write_bytes(b"fake audio bytes" * 50)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    import_material(connection, media, subtitle, "Lesson One")

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")

    assert window._material_list.count() == 1
    item = window._material_list.item(0)
    assert item.text() == "Lesson One"

    window._material_list.setCurrentItem(item)
    assert "Lesson One" in window._detail_label.text()
    assert "Cue count: 1" in window._detail_label.text()
    assert window._rename_button.isEnabled()

    window.close()


def test_main_window_double_click_opens_player_for_active_material(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    import_material(connection, media, subtitle, "Lesson One")

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    item = window._material_list.item(0)
    window._on_material_double_clicked(item)

    assert window._player_window is not None
    assert "Lesson One" in window._player_window.windowTitle()

    window._player_window.close()
    window.close()


def test_open_player_button_disabled_in_archived_view(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    library.archive_material(connection, result.material_id)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._on_toggle_archived()

    assert window._material_list.count() == 1
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._open_player_button.isEnabled() is False

    window.close()


def test_double_click_in_archived_view_does_not_open_player(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    library.archive_material(connection, result.material_id)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._on_toggle_archived()
    item = window._material_list.item(0)
    window._on_material_double_clicked(item)

    assert window._player_window is None

    window.close()


def test_start_intensive_practice_opens_guided_window_and_enables_resume(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._resume_intensive_button.isEnabled() is False

    window._on_start_intensive_clicked()

    assert window._guided_session_window is not None
    assert session_service.find_active_session(connection, result.material_id) is not None
    assert window._resume_intensive_button.isEnabled() is True

    window._guided_session_window.close()
    window.close()


def test_start_intensive_practice_with_active_session_offers_resume_choice(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    existing = session_service.start_session(connection, result.material_id)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    window._on_start_intensive_clicked()

    # "Yes" maps to Resume: no second session should be created.
    sessions = session_service.list_sessions_for_material(connection, result.material_id)
    assert len(sessions) == 1
    assert sessions[0].id == existing.id

    window._guided_session_window.close()
    window.close()


def test_start_intensive_practice_abandon_and_start_new(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    existing = session_service.start_session(connection, result.material_id)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    window._on_start_intensive_clicked()

    sessions = session_service.list_sessions_for_material(connection, result.material_id)
    assert len(sessions) == 2
    old_session = next(s for s in sessions if s.id == existing.id)
    assert old_session.status == "abandoned"
    new_session = next(s for s in sessions if s.id != existing.id)
    assert new_session.status == "active"

    window._guided_session_window.close()
    window.close()


def test_resume_intensive_practice_button_opens_active_session(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    session_service.start_session(connection, result.material_id)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._resume_intensive_button.isEnabled() is True

    window._on_resume_intensive_clicked()
    assert window._guided_session_window is not None

    window._guided_session_window.close()
    window.close()


def test_session_history_dialog_opens_selected_session(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    first = session_service.start_session(connection, result.material_id)
    session_service.abandon_session(connection, first.id)
    second = session_service.start_session(connection, result.material_id)
    session_service.abandon_session(connection, second.id)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))

    from listentrace.ui.windows.session_history_dialog import SessionHistoryDialog

    dialog = SessionHistoryDialog(connection, result.material_id, "Lesson One", window)
    assert dialog._list.count() == 2
    dialog._list.setCurrentRow(0)
    dialog._on_open_clicked()
    assert dialog.selected_session_id in (first.id, second.id)

    window._open_guided_session(result.material_id, dialog.selected_session_id)
    assert window._guided_session_window is not None
    # A closed (abandoned) session opens read-only.
    assert window._guided_session_window._continue_button.isEnabled() is False

    window._guided_session_window.close()
    window.close()


def test_session_history_dialog_delete_requires_confirmation_and_removes_the_row(qapp, tmp_path, monkeypatch):
    """M12 History Ownership Contract (m05-02): the user can delete a
    completed/abandoned Guided Session from history, but not an active one."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    abandoned = session_service.start_session(connection, result.material_id)
    session_service.abandon_session(connection, abandoned.id)
    active = session_service.start_session(connection, result.material_id)

    from listentrace.ui.windows.session_history_dialog import SessionHistoryDialog

    dialog = SessionHistoryDialog(connection, result.material_id, "Lesson One")
    assert dialog._list.count() == 2

    active_row = next(i for i in range(2) if dialog._list.item(i).data(Qt.ItemDataRole.UserRole) == active.id)
    dialog._list.setCurrentRow(active_row)
    assert dialog._delete_button.isEnabled() is False, "an active session must not be deletable"

    abandoned_row = 1 - active_row
    dialog._list.setCurrentRow(abandoned_row)
    assert dialog._delete_button.isEnabled() is True

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog._on_delete_clicked()

    assert dialog._list.count() == 1
    assert session_service.get_session(connection, abandoned.id) is None
    assert session_service.get_session(connection, active.id) is not None
    dialog.close()


def test_start_material_quiz_opens_quiz_window_and_enables_resume(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")

    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (3, True))

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._resume_quiz_button.isEnabled() is False

    window._on_start_material_quiz_clicked()

    assert window._quiz_window is not None
    active = quiz_service.find_active_quizzes_for_material(connection, result.material_id)
    assert len(active) == 1
    assert window._resume_quiz_button.isEnabled() is True

    window._quiz_window.close()
    window.close()


def test_start_material_quiz_cancelled_input_dialog_does_not_create_a_quiz(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")

    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (3, False))

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    window._on_start_material_quiz_clicked()

    assert window._quiz_window is None
    assert quiz_service.find_active_quizzes_for_material(connection, result.material_id) == []

    window.close()


def test_start_review_quiz_without_diagnosis_evidence_shows_a_warning(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    import_material(connection, media, subtitle, "Lesson One")

    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (3, True))
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok
    )

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    window._on_start_review_quiz_clicked()

    assert window._quiz_window is None
    assert len(warnings) == 1

    window.close()


def test_resume_quiz_button_opens_active_quiz(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    quiz_service.create_material_quiz(connection, result.material_id, requested_count=3, seed=1)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._resume_quiz_button.isEnabled() is True

    window._on_resume_quiz_clicked()
    assert window._quiz_window is not None

    window._quiz_window.close()
    window.close()


def test_quiz_history_dialog_opens_selected_quiz(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    first = quiz_service.create_material_quiz(connection, result.material_id, requested_count=2, seed=1)
    quiz_service.abandon_quiz(connection, first.id)
    second = quiz_service.create_material_quiz(connection, result.material_id, requested_count=2, seed=2)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))

    from listentrace.ui.windows.quiz_history_dialog import QuizHistoryDialog

    dialog = QuizHistoryDialog(connection, result.material_id, "Lesson One", window)
    assert dialog._list.count() == 2
    dialog._list.setCurrentRow(0)
    dialog._on_open_clicked()
    assert dialog.selected_attempt_id in (first.id, second.id)

    window._open_quiz(result.material_id, dialog.selected_attempt_id)
    assert window._quiz_window is not None

    window._quiz_window.close()
    window.close()


def test_quiz_history_dialog_delete_requires_confirmation_and_removes_the_row(qapp, tmp_path, monkeypatch):
    """M12 History Ownership Contract (m05-02): the user can delete a
    completed/abandoned quiz attempt from history, but not an active one."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    active = quiz_service.create_material_quiz(connection, result.material_id, requested_count=2, seed=1)
    abandoned = quiz_service.create_material_quiz(connection, result.material_id, requested_count=2, seed=2)
    quiz_service.abandon_quiz(connection, abandoned.id)

    from listentrace.ui.windows.quiz_history_dialog import QuizHistoryDialog

    dialog = QuizHistoryDialog(connection, result.material_id, "Lesson One")
    assert dialog._list.count() == 2

    active_row = next(i for i in range(2) if dialog._list.item(i).data(Qt.ItemDataRole.UserRole) == active.id)
    dialog._list.setCurrentRow(active_row)
    assert dialog._delete_button.isEnabled() is False, "an active attempt must not be deletable"

    abandoned_row = 1 - active_row
    dialog._list.setCurrentRow(abandoned_row)
    assert dialog._delete_button.isEnabled() is True

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog._on_delete_clicked()

    assert dialog._list.count() == 1
    assert quiz_service.get_quiz_attempt(connection, abandoned.id) is None
    assert quiz_service.get_quiz_attempt(connection, active.id) is not None
    dialog.close()


def test_quiz_window_material_renamed_updates_title_and_header(qapp, tmp_path):
    """M14 Corrective Batch A (A2): rename propagation to an already-open
    dependent window."""
    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.widgets.material_metadata_bus import material_metadata_bus
    from listentrace.ui.windows.quiz_window import QuizWindow

    connection = open_connection(tmp_path / "smoke_quiz_rename.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Quiz Lesson")
    attempt = quiz_service.create_material_quiz(connection, result.material_id, requested_count=5, seed=1)

    load_result = load_material_for_player(connection, result.material_id)
    quiz_window = QuizWindow(connection, load_result, attempt.id, None)

    assert quiz_window.windowTitle() == "ListenTrace — Quiz — Quiz Lesson"
    assert quiz_window._header_title_label.text() == "Quiz Lesson"

    material_metadata_bus.material_renamed.emit(result.material_id, "Renamed Quiz Lesson")

    assert quiz_window.windowTitle() == "ListenTrace — Quiz — Renamed Quiz Lesson"
    assert quiz_window._header_title_label.text() == "Renamed Quiz Lesson"
    assert quiz_window._material.title == "Renamed Quiz Lesson"

    quiz_window.close()
    connection.close()


def test_quiz_window_full_take_submit_and_review_flow(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    attempt = quiz_service.create_material_quiz(connection, result.material_id, requested_count=5, seed=1)

    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.quiz_window import QuizWindow

    load_result = load_material_for_player(connection, result.material_id)
    quiz_window = QuizWindow(connection, load_result, attempt.id, None)

    import json

    from listentrace.domain.enums.question_type import QuestionType

    state = quiz_service.load_quiz_state(connection, attempt.id)
    for index, question in enumerate(state.questions):
        quiz_window._show_question(index)
        correct = json.loads(question.correct_answer_payload)
        if question.question_type in (QuestionType.DICTATION.value, QuestionType.REVIEW_MISSED.value):
            quiz_window._answer_line_edit.setText(correct["answer_text"])
        else:
            quiz_window._choice_radio_buttons[correct["correct_choice_index"]].setChecked(True)
    quiz_window._save_current_answer()

    quiz_window._save_current_answer()
    quiz_service.submit_quiz(connection, attempt.id)
    quiz_window._refresh_state()

    completed = quiz_service.get_quiz_attempt(connection, attempt.id)
    assert completed.status == "completed"
    assert completed.correct_count == len(state.questions)
    assert quiz_window._review_button.isEnabled() is True

    from listentrace.ui.windows.quiz_review_dialog import QuizReviewDialog

    review_dialog = QuizReviewDialog(connection, attempt.id, quiz_window)
    assert review_dialog._list.count() == len(state.questions)

    review_dialog.close()
    quiz_window.close()


def test_quiz_window_loop_settings_button_opens_a_material_loop_settings_dialog(qapp, tmp_path):
    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog
    from listentrace.ui.windows.quiz_window import QuizWindow

    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    attempt = quiz_service.create_material_quiz(connection, result.material_id, requested_count=5, seed=1)
    load_result = load_material_for_player(connection, result.material_id)
    quiz_window = QuizWindow(connection, load_result, attempt.id, None)

    quiz_window._on_open_loop_settings()

    assert isinstance(quiz_window._loop_settings_dialog, MaterialLoopSettingsDialog)
    quiz_window.close()


def test_quiz_window_material_override_changed_updates_its_live_session_grace(qapp, tmp_path):
    from listentrace.application.services import loop_grace_service
    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
    from listentrace.ui.windows.quiz_window import QuizWindow

    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    attempt = quiz_service.create_material_quiz(connection, result.material_id, requested_count=5, seed=1)
    load_result = load_material_for_player(connection, result.material_id)
    quiz_window = QuizWindow(connection, load_result, attempt.id, None)

    loop_grace_service.set_material_loop_end_grace_override_ms(connection, result.material_id, 90)
    loop_grace_change_bus.material_override_changed.emit(result.material_id)

    assert quiz_window._player_session._loop_end_grace_ms == 90
    quiz_window.close()


def test_quiz_window_play_button_is_cue_scoped_not_whole_media(qapp, tmp_path):
    """M12 Round 1 Playback Contract (m05-01/m10-05/m12-05, P1): Play in a
    cue-oriented context must stop at the current cue's end, never drift into
    the next cue's audio, the way whole-media continuous playback would."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media, seconds=11)  # covers all of _MULTI_CUE_SRT's 0-10000ms range
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    attempt = quiz_service.create_material_quiz(connection, result.material_id, requested_count=5, seed=1)

    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.quiz_window import QuizWindow

    load_result = load_material_for_player(connection, result.material_id)
    quiz_window = QuizWindow(connection, load_result, attempt.id, None)
    _pump(500)  # let the async media load finish before seeking away from position 0

    state = quiz_service.load_quiz_state(connection, attempt.id)
    cue_index = quiz_window._cue_index_by_id[state.questions[0].subtitle_cue_id]
    cue = quiz_window._player_session.cues[cue_index]

    quiz_window._show_question(0)
    quiz_window._on_play_clicked()
    _pump((cue.end_ms - cue.start_ms) + 500)  # long enough to cross the cue boundary if unbounded

    assert quiz_window._playback.is_playing is False, (
        "Play must stop at this cue's end, not continue playing into the next cue"
    )
    assert quiz_window._playback.position_ms < cue.end_ms + 200

    quiz_window.close()


def test_quiz_choice_options_wrap_long_text_instead_of_truncating(qapp, tmp_path):
    """M12 Round 2 Layout Contract (m05-01, L2): a long answer option was
    hard-truncated with an ellipsis on a bare QRadioButton, which has no
    word-wrap support in Qt Widgets at all -- confirmed during Phase 0 by
    screenshot. The option text must now live on a paired, wrapping QLabel."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    attempt = quiz_service.create_material_quiz(connection, result.material_id, requested_count=5, seed=1)

    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.quiz_window import QuizWindow

    load_result = load_material_for_player(connection, result.material_id)
    quiz_window = QuizWindow(connection, load_result, attempt.id, None)

    import json

    state = quiz_service.load_quiz_state(connection, attempt.id)
    choice_question = next(
        q for q in state.questions if q.question_type not in ("dictation", "review_missed")
    )
    index = state.questions.index(choice_question)
    quiz_window._show_question(index)

    choices = json.loads(choice_question.prompt_payload)["choices"]
    for i, choice_text in enumerate(choices):
        label = quiz_window._choice_labels[i]
        assert label.wordWrap() is True
        assert label.text() == choice_text, "the full option text must reach the label untruncated"
        # The radio itself must never carry the option text -- QRadioButton
        # has no word-wrap support at all, which is exactly what produced
        # the truncated ellipsis in the human-QA screenshot.
        assert quiz_window._choice_radio_buttons[i].text() == ""

    quiz_window.close()


def test_quiz_window_abandon_makes_it_read_only(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    attempt = quiz_service.create_material_quiz(connection, result.material_id, requested_count=3, seed=1)

    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.quiz_window import QuizWindow

    load_result = load_material_for_player(connection, result.material_id)
    quiz_window = QuizWindow(connection, load_result, attempt.id, None)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    quiz_window._on_abandon_clicked()

    abandoned = quiz_service.get_quiz_attempt(connection, attempt.id)
    assert abandoned.status == "abandoned"


# ---- Milestone 7: shadowing and local recording ----


def _write_valid_wav(path, seconds=1, framerate=8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _import_shadowing_lesson(connection, tmp_path):
    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    return import_material(connection, media, subtitle, "Lesson One")


def test_shadowing_practice_button_opens_window_for_selected_material(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._shadowing_practice_button.isEnabled() is True

    window._on_shadowing_practice_clicked()

    assert window._shadowing_practice_window is not None
    assert window._shadowing_practice_window.windowTitle().endswith("Lesson One")

    window._shadowing_practice_window.close()
    window.close()


def test_shadowing_practice_window_cue_navigation_updates_recording_context(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow

    load_result = load_material_for_player(connection, result.material_id)
    window = ShadowingPracticeWindow(connection, load_result, tmp_path / "recordings")

    first_cue_id = window._recording_panel._subtitle_cue_id
    assert first_cue_id == load_result.cues[0].id

    window._on_next_clicked()

    assert window._recording_panel._subtitle_cue_id == load_result.cues[1].id
    assert window._recording_panel._subtitle_cue_id != first_cue_id
    assert window._recording_panel._practice_session_id is None

    window.close()


def test_shadowing_practice_window_lists_an_existing_take_for_the_current_cue(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic"
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)

    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow

    load_result = load_material_for_player(connection, result.material_id)
    window = ShadowingPracticeWindow(connection, load_result, recordings_dir)

    assert window._recording_panel._takes_list.count() == 1
    assert "Take #" in window._recording_panel._takes_list.item(0).text()

    window.close()


def test_recording_panel_delete_take_button_removes_row_and_file(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic"
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)

    from listentrace.ui.widgets.recording_panel import RecordingPanel

    panel = RecordingPanel(connection, recordings_dir)
    panel.set_context(result.material_id, first_cue.id, None)
    assert panel._takes_list.count() == 1

    panel._takes_list.setCurrentRow(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    panel._on_delete_take_clicked()

    assert panel._takes_list.count() == 0
    assert not path.exists()
    assert recording_service.get_take(connection, recording.id) is None

    panel.close()


def test_recording_panel_can_delete_a_take_immediately_after_playing_it(qapp, tmp_path, monkeypatch):
    """Regression test: a stopped QMediaPlayer keeps its source file locked on
    Windows until the source is explicitly cleared. Playing a take and then
    deleting it right afterward must still succeed — caught by the Milestone 7
    real-microphone manual smoke test, where "Compare" (which plays a take)
    followed by "Delete Take" on the same recording used to fail with
    file_deletion_failed."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic"
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)

    from listentrace.ui.widgets.recording_panel import RecordingPanel

    panel = RecordingPanel(connection, recordings_dir)
    panel.set_context(result.material_id, first_cue.id, None)
    panel._takes_list.setCurrentRow(0)

    panel._on_play_take_clicked()
    _pump(300)

    panel._takes_list.setCurrentRow(0)
    warnings_seen: list[str] = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings_seen.append(str(a)))
    panel._on_delete_take_clicked()

    assert warnings_seen == []
    assert panel._takes_list.count() == 0
    assert not path.exists()

    panel.close()


def _fake_device() -> "AudioInputDevice":
    from listentrace.infrastructure.media.recording import AudioInputDevice

    return AudioInputDevice(device_id="fake-device-1", description="Fake Test Microphone", is_default=True)


def test_recording_panel_set_context_enables_start_recording_once_device_and_cue_are_set(qapp, tmp_path, monkeypatch):
    """Regression test: set_context() used to only call _refresh_takes(), never
    _update_recording_buttons() -- so Start Recording stayed stuck disabled
    (computed once at construction time, before any cue existed) even after a
    real context with a device and a cue was set. GuidedSessionWindow and
    QuickPracticeWindow masked this because they always call set_read_only()
    right after set_context(), which happens to refresh the buttons as a side
    effect; ShadowingPracticeWindow never calls set_read_only() at all, so the
    bug was fully exposed there."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.widgets.recording_panel import RecordingPanel

    monkeypatch.setattr(recording_service, "list_audio_input_devices", lambda: [_fake_device()])

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    panel = RecordingPanel(connection, tmp_path / "recordings")
    # At construction time no cue is set yet -- Start Recording is correctly
    # disabled even though a device was auto-selected.
    assert panel._start_recording_button.isEnabled() is False

    panel.set_context(result.material_id, first_cue.id, None)

    assert panel._start_recording_button.isEnabled() is True
    panel.close()


def test_recording_panel_set_context_keeps_start_recording_disabled_without_a_device(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.widgets.recording_panel import RecordingPanel

    monkeypatch.setattr(recording_service, "list_audio_input_devices", lambda: [])

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    panel = RecordingPanel(connection, tmp_path / "recordings")
    panel.set_context(result.material_id, first_cue.id, None)

    assert panel._device_status_label.text() == "No microphone was found on this system."
    assert panel._start_recording_button.isEnabled() is False
    panel.close()


def test_recording_panel_set_context_respects_read_only(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.widgets.recording_panel import RecordingPanel

    monkeypatch.setattr(recording_service, "list_audio_input_devices", lambda: [_fake_device()])

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    panel = RecordingPanel(connection, tmp_path / "recordings")
    panel.set_read_only(True)

    panel.set_context(result.material_id, first_cue.id, None)

    assert panel._start_recording_button.isEnabled() is False
    panel.close()


def test_recording_panel_set_context_refreshes_buttons_on_cue_switch(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.widgets.recording_panel import RecordingPanel

    monkeypatch.setattr(recording_service, "list_audio_input_devices", lambda: [_fake_device()])

    track = get_subtitle_track_for_material(connection, result.material_id)
    cues = get_cues_for_track(connection, track.id)
    assert len(cues) >= 2

    panel = RecordingPanel(connection, tmp_path / "recordings")
    panel.set_context(result.material_id, cues[0].id, None)
    assert panel._start_recording_button.isEnabled() is True

    panel.set_context(result.material_id, cues[1].id, None)
    assert panel._start_recording_button.isEnabled() is True
    panel.close()


def test_guided_session_stage4_recording_panel_syncs_to_current_shadowing_cue(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    session = session_service.start_session(connection, result.material_id)

    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.ui.windows.guided_session_window import GuidedSessionWindow

    load_result = load_material_for_player(connection, result.material_id)
    window = GuidedSessionWindow(connection, load_result, session.id, tmp_path / "recordings")
    window._show_stage("shadowing")

    assert window._recording_panel._subtitle_cue_id == load_result.cues[0].id
    assert window._recording_panel._practice_session_id == session.id

    window._on_shadowing_next_clicked()

    assert window._recording_panel._subtitle_cue_id == load_result.cues[1].id

    window.close()


def test_guided_session_stage4_recording_does_not_alter_mark_practiced_flow(qapp, tmp_path):
    """Creating/finishing a recording must not itself mark a cue practiced, and
    marking a cue practiced must not disturb an already-listed take — the two
    are fully independent, per the Milestone 7 product boundary."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"
    session = session_service.start_session(connection, result.material_id)
    session_service.enter_stage(connection, session.id, "shadowing")

    from listentrace.application.services import recording_service
    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.windows.guided_session_window import GuidedSessionWindow

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic",
        practice_session_id=session.id,
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)

    load_result = load_material_for_player(connection, result.material_id)
    window = GuidedSessionWindow(connection, load_result, session.id, recordings_dir)
    window._show_stage("shadowing")
    assert window._recording_panel._takes_list.count() == 1

    window._on_mark_practiced_clicked()

    state = session_service.load_session_state(connection, session.id)
    progress = next(p for p in state.shadowing_progress if p.subtitle_cue_id == first_cue.id)
    assert progress.status == "practiced"
    # The take created before "Mark Practiced" must still be there, untouched.
    assert window._recording_panel._takes_list.count() == 1
    assert recording_service.get_take(connection, recording.id).status == "ready"

    window.close()


def test_remove_material_deletes_recording_files_from_disk(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic"
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)
    assert path.exists()

    summary = library.remove_material(connection, recordings_dir, result.material_id)

    assert summary.all_succeeded
    assert not path.exists()


def test_main_window_remove_material_is_aborted_when_a_recording_file_cannot_be_deleted(qapp, tmp_path, monkeypatch):
    """Milestone 7 acceptance correction: a material must not be removed (nor
    its recording rows cascade-deleted) if any recording file fails to
    delete — never create an untracked orphan file, and let the learner
    retry."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic"
    )
    # Force the eventual unlink() to fail: a directory sits where the file should be.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()
    recording_service.finish_recording(connection, recordings_dir, recording.id)  # -> failed, file left as a dir

    window = MainWindow(connection, tmp_path / "smoke.db", recordings_dir)
    window._material_list.setCurrentItem(window._material_list.item(0))

    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda self, title, text, *a, **k: warnings.append(title))

    window._on_remove_clicked()

    assert any("Cannot Remove Material" in title for title in warnings)
    # The material and the still-failed recording row must both survive, so
    # the learner can retry after fixing the underlying issue.
    from listentrace.application.services import material_library_service as library

    assert library.get_material_detail(connection, result.material_id) is not None
    assert recording_service.get_take(connection, recording.id) is not None
    window.close()


def test_remove_material_confirmation_mentions_recordings_will_be_deleted(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _import_shadowing_lesson(connection, tmp_path)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))

    captured_text: list[str] = []

    def fake_question(self, title, text, *a, **k):
        captured_text.append(text)
        return QMessageBox.StandardButton.No  # decline — this test only checks the wording

    monkeypatch.setattr(QMessageBox, "question", fake_question)
    window._on_remove_clicked()

    assert captured_text and "recording" in captured_text[0].lower()
    window.close()


def test_recording_panel_leaves_device_unselected_when_saved_device_is_unavailable(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)

    from listentrace.application.services import recording_service
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.infrastructure.media.recording import AudioInputDevice
    from listentrace.ui.widgets.recording_panel import RecordingPanel

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    device_a = AudioInputDevice(device_id="aaa", description="Mic A", is_default=True)
    monkeypatch.setattr(recording_service, "list_audio_input_devices", lambda: [device_a])
    recording_service.remember_device_choice(connection, "vanished-id", "Old Mic")

    panel = RecordingPanel(connection, tmp_path / "recordings")
    panel.set_context(result.material_id, first_cue.id, None)

    assert panel._device_combo.currentIndex() == -1
    assert panel._selected_device() is None
    assert "no longer available" in panel._device_status_label.text()
    assert panel._start_recording_button.isEnabled() is False

    # Explicitly choosing the available device must enable Start Recording.
    panel._device_combo.setCurrentIndex(0)
    assert panel._selected_device() is not None
    assert panel._start_recording_button.isEnabled() is True

    panel.close()


def test_guided_session_comparison_cancelled_on_source_playback_error(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"
    session = session_service.start_session(connection, result.material_id)
    session_service.enter_stage(connection, session.id, "shadowing")

    from listentrace.application.services import recording_service
    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.windows.guided_session_window import GuidedSessionWindow

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic",
        practice_session_id=session.id,
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)

    load_result = load_material_for_player(connection, result.material_id)
    window = GuidedSessionWindow(connection, load_result, session.id, recordings_dir)
    window._show_stage("shadowing")

    panel = window._recording_panel
    panel._takes_list.setCurrentRow(0)
    panel._on_compare_clicked()
    assert panel._sequencer.is_active

    window._on_playback_error("simulated device failure")

    assert not panel._sequencer.is_active
    panel._takes_list.setCurrentRow(0)
    assert panel._play_take_button.isEnabled() is True
    assert panel._delete_take_button.isEnabled() is True

    window.close()


def test_loop_restart_tick_does_not_falsely_finish_a_stale_pending_comparison(qapp, tmp_path):
    """Regression: starting Loop Cue while a comparison replay is still
    pending (e.g. the learner clicks Loop before the comparison finishes)
    overwrites PlayerSession's `_active_span` without the window ever
    clearing `_comparison_replay_pending` -- that flag is window-level
    bookkeeping PlayerSession knows nothing about. A tick from that Loop
    completing is still `pause=True` (every bounded-span completion is), so
    the comparison-finished check must also require `restart_at_ms is None`
    to stay mutually exclusive with a Loop restart, exactly as the original
    single `elif tick.pause:` branch guaranteed before `_apply_player_tick`
    was extracted -- otherwise a Loop's own automatic restart would
    incorrectly report the abandoned comparison as successfully finished."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"

    from listentrace.application.services import recording_service
    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic"
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)

    load_result = load_material_for_player(connection, result.material_id)
    window = ShadowingPracticeWindow(connection, load_result, recordings_dir)

    panel = window._recording_panel
    panel._takes_list.setCurrentRow(0)
    panel._on_compare_clicked()
    assert window._comparison_replay_pending is True

    # The learner clicks Loop before the comparison ever reaches its own
    # pause boundary -- this overwrites PlayerSession's _active_span with a
    # new Loop span; `_comparison_replay_pending` is untouched by design
    # (PlayerSession has no notion of it).
    window._on_loop_clicked()
    assert window._comparison_replay_pending is True, "still stale, not yet reconciled by any tick"

    finished_calls = []
    panel.notify_source_finished = lambda: finished_calls.append(True)

    from listentrace.domain.services.loop_grace_policy import LOOP_END_GRACE_DEFAULT_MS

    # crosses the loop span's *effective* completion end (logical end + grace,
    # since loop_mode is now active) -- not the bare cue end.
    window._on_position_changed(first_cue.end_ms + LOOP_END_GRACE_DEFAULT_MS)

    assert finished_calls == [], "a Loop restart must never be reported as a finished comparison"
    assert window._comparison_replay_pending is True

    window.close()


def test_shadowing_practice_comparison_cancelled_when_source_ends_before_finishing(qapp, tmp_path):
    """The "cannot finish" case: the media ends before the one-shot source
    replay's own tick-based pause boundary is ever reached, so the comparison
    can never advance normally."""
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    result = _import_shadowing_lesson(connection, tmp_path)
    recordings_dir = tmp_path / "recordings"

    from listentrace.application.services import recording_service
    from listentrace.application.services.player_loading_service import load_material_for_player
    from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
    from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow

    track = get_subtitle_track_for_material(connection, result.material_id)
    first_cue = get_cues_for_track(connection, track.id)[0]

    recording, path = recording_service.begin_recording(
        connection, recordings_dir, result.material_id, first_cue.id, "dev-1", "Test Mic"
    )
    _write_valid_wav(path, seconds=1)
    recording_service.finish_recording(connection, recordings_dir, recording.id)

    load_result = load_material_for_player(connection, result.material_id)
    window = ShadowingPracticeWindow(connection, load_result, recordings_dir)

    panel = window._recording_panel
    panel._takes_list.setCurrentRow(0)
    panel._on_compare_clicked()
    assert panel._sequencer.is_active
    assert window._comparison_replay_pending is True

    window._on_end_of_media()

    assert window._comparison_replay_pending is False
    assert not panel._sequencer.is_active
    panel._takes_list.setCurrentRow(0)
    assert panel._play_take_button.isEnabled() is True
    assert panel._delete_take_button.isEnabled() is True

    window.close()
