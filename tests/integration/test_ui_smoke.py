from __future__ import annotations

import struct
import wave

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

    window = MainWindow(connection, db_path)

    assert window.windowTitle() == "ListenTrace"
    assert "Schema version: 6" in window._status_label.text()

    window.close()


def test_main_window_shows_empty_library_state(qapp, tmp_path):
    connection = open_connection(tmp_path / "empty.db")
    migrate(connection)

    window = MainWindow(connection, tmp_path / "empty.db")

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

    window = MainWindow(connection, tmp_path / "smoke.db")

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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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


def test_start_material_quiz_opens_quiz_window_and_enables_resume(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text(_MULTI_CUE_SRT, encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")

    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (3, True))

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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

    window = MainWindow(connection, tmp_path / "smoke.db")
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
