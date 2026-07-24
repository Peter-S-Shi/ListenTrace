from __future__ import annotations

import uuid

from listentrace.domain.models.material import Material
from listentrace.domain.models.quiz_attempt import QuizAttempt
from listentrace.domain.models.quiz_question import QuizQuestion
from listentrace.domain.models.recording import Recording
from listentrace.domain.models.session_diagnosis_evidence import SessionDiagnosisEvidence
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.domain.services import date_range as date_range_rules
from listentrace.infrastructure.db import quiz_repository, recording_repository, session_repository
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_subtitle_track_for_material,
    insert_material,
    insert_subtitle_track,
)
from listentrace.ui.windows.learning_history_window import _PRESET_LABELS, LearningHistoryWindow
from listentrace.ui.windows.main_window import MainWindow
from listentrace.ui.windows.quiz_review_dialog import QuizReviewDialog


def _make_material_with_cues(conn, tmp_path, title="Lesson"):
    media_path = tmp_path / f"{title}.mp4"
    media_path.write_bytes(b"fake media bytes" * 10)
    subtitle_path = tmp_path / f"{title}.srt"
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")

    material_id = insert_material(conn, Material(title=title, media_path=str(media_path)))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path=str(subtitle_path),
        cues=[
            SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour"),
            SubtitleCue(cue_index=2, start_ms=1000, end_ms=2000, text="Au revoir"),
        ],
    )
    insert_subtitle_track(conn, track)
    track_row = get_subtitle_track_for_material(conn, material_id)
    cues = get_cues_for_track(conn, track_row.id)
    return material_id, cues


def _seed_rich_material(conn, tmp_path):
    material_id, cues = _make_material_with_cues(conn, tmp_path)

    session_id = session_repository.create_practice_session(conn, material_id)
    session_repository.set_session_status(conn, session_id, "completed")
    session_repository.set_stage_status(conn, session_id, "shadowing", "skipped", skip_note="ran out of time")

    session_repository.ensure_shadowing_rows(conn, session_id, [c.id for c in cues])
    session_repository.mark_shadowing_practiced(conn, session_id, cues[0].id)

    evidence = SessionDiagnosisEvidence(
        practice_session_id=session_id,
        subtitle_cue_id=cues[0].id,
        label_key="misheard",
        selected_text="Bonjour",
        selection_start=0,
        selection_end=7,
        heard_as="Bonjoir",
    )
    session_repository.insert_session_diagnosis(conn, evidence)

    attempt = QuizAttempt(material_id=material_id, requested_count=2)
    question = QuizQuestion(
        question_type="dictation",
        subtitle_cue_id=cues[0].id,
        source_cue_text="Bonjour",
        prompt_payload="{}",
        correct_answer_payload="{}",
        scoring_config='{"rule": "normalized_text_exact", "version": 1}',
    )
    attempt_id, _ = quiz_repository.create_quiz_attempt_with_questions(conn, attempt, [question, question])
    quiz_repository.finalize_quiz_score(conn, attempt_id, 1)

    recording = Recording(
        material_id=material_id,
        subtitle_cue_id=cues[0].id,
        practice_session_id=session_id,
        relative_file_path=f"{material_id}/{uuid.uuid4().hex}.wav",
    )
    recording_id = recording_repository.insert_recording(conn, recording)
    recording_repository.set_recording_ready(conn, recording_id, 1500)
    conn.commit()

    return material_id, cues, session_id, attempt_id, recording_id


def test_window_opens_with_no_data(qapp, tmp_path):
    connection = open_connection(tmp_path / "empty.db")
    migrate(connection)

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    assert "No active sessions." in [
        window._continue_learning_list.item(i).text() for i in range(window._continue_learning_list.count())
    ]
    assert "No materials currently need attention." in [
        window._needs_attention_list.item(i).text() for i in range(window._needs_attention_list.count())
    ]
    window.close()


def test_main_window_opens_learning_history_globally_without_a_selected_material(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._on_learning_history_clicked()

    assert window._learning_history_window is not None
    assert window._learning_history_window._selected_material_id() is None
    window._learning_history_window.close()
    window.close()


def test_overview_reflects_seeded_evidence(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_id, cues, session_id, attempt_id, recording_id = _seed_rich_material(connection, tmp_path)

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    overview_text = window._overview_label.text()
    assert "Completed Sessions: 1" in overview_text
    assert "Completed Quizzes: 1" in overview_text
    assert "Session Diagnosis Evidence: 1" in overview_text
    assert "Retained Recordings: 1" in overview_text
    assert window._sessions_list.count() == 1
    assert window._quiz_history_list.count() == 1
    assert window._diagnosis_history_list.count() == 1
    assert window._shadowing_list.count() == 1
    assert window._recording_list.count() == 1
    window.close()


def test_material_filter_scopes_the_reload(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_a, cues_a, *_ = _seed_rich_material(connection, tmp_path)
    material_b, _ = _make_material_with_cues(connection, tmp_path, title="Other")

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    index = window._material_combo.findData(material_b)
    assert index >= 0
    window._material_combo.setCurrentIndex(index)

    assert window._sessions_list.count() == 1  # placeholder "no sessions" row
    assert window._session_entries == []
    window.close()


def test_custom_date_range_shows_date_edits_only_when_selected(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    window = LearningHistoryWindow(connection, tmp_path / "recordings")

    assert window._custom_start_edit.isHidden()
    custom_index = next(i for i, (_, preset) in enumerate(_PRESET_LABELS) if preset == date_range_rules.PRESET_CUSTOM)
    window._preset_combo.setCurrentIndex(custom_index)
    assert window._current_preset() == date_range_rules.PRESET_CUSTOM
    assert not window._custom_start_edit.isHidden()
    window.close()


def test_needs_attention_double_click_sets_material_filter(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_id, _ = _make_material_with_cues(connection, tmp_path)
    session_repository.create_practice_session(connection, material_id)  # stays active

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    assert window._needs_attention_list.count() == 1
    item = window._needs_attention_list.item(0)
    window._on_needs_attention_double_clicked(item)
    assert window._selected_material_id() == material_id
    window.close()


def test_continue_learning_resume_opens_guided_session(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_id, cues = _make_material_with_cues(connection, tmp_path)
    session_repository.create_practice_session(connection, material_id)

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    assert window._continue_learning_list.count() == 1
    window._continue_learning_list.setCurrentRow(0)
    assert window._resume_button.isEnabled()

    window._on_resume_clicked()
    assert window._child_window is not None
    assert "Lesson" in window._child_window.windowTitle()
    window._child_window.close()
    window.close()


def test_abandon_session_from_continue_learning(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_id, _ = _make_material_with_cues(connection, tmp_path)
    session_id = session_repository.create_practice_session(connection, material_id)

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    window._continue_learning_list.setCurrentRow(0)

    from PySide6.QtWidgets import QMessageBox

    original_question = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        window._on_abandon_clicked()
    finally:
        QMessageBox.question = original_question

    from listentrace.application.services import practice_session_service

    session = practice_session_service.get_session(connection, session_id)
    assert session.status == "abandoned"
    assert window._continue_learning_list.count() == 1  # placeholder "no active sessions"
    window.close()


def test_activity_type_filter_hides_unchecked_types(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _seed_rich_material(connection, tmp_path)

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    assert window._activity_list.count() >= 3

    for activity_type, checkbox in window._activity_checkboxes.items():
        if activity_type != "quiz":
            checkbox.setChecked(False)

    texts = [window._activity_list.item(i).text() for i in range(window._activity_list.count())]
    assert all("quiz" in t.lower() for t in texts)
    window.close()


def test_quiz_trend_group_selector_never_mixes_materials_or_modes(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_a, cues_a = _make_material_with_cues(connection, tmp_path, title="A")
    material_b, cues_b = _make_material_with_cues(connection, tmp_path, title="B")

    def _make_completed_attempt(material_id, cue_id, correct, actual, quiz_mode="material"):
        attempt = QuizAttempt(material_id=material_id, quiz_mode=quiz_mode, requested_count=actual)
        question = QuizQuestion(
            question_type="dictation",
            subtitle_cue_id=cue_id,
            source_cue_text="Bonjour",
            prompt_payload="{}",
            correct_answer_payload="{}",
            scoring_config='{"rule": "normalized_text_exact", "version": 1}',
        )
        attempt_id, _ = quiz_repository.create_quiz_attempt_with_questions(connection, attempt, [question] * actual)
        quiz_repository.finalize_quiz_score(connection, attempt_id, correct)
        connection.commit()
        return attempt_id

    _make_completed_attempt(material_a, cues_a[0].id, 1, 4, quiz_mode="material")
    _make_completed_attempt(material_a, cues_a[0].id, 3, 4, quiz_mode="review")
    _make_completed_attempt(material_b, cues_b[0].id, 2, 4, quiz_mode="material")

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    # Three distinct (material, mode) groups were seeded; the combo must
    # offer all three rather than silently collapsing any of them.
    assert window._quiz_trend_group_combo.count() == 3

    seen_point_counts = set()
    for index in range(window._quiz_trend_group_combo.count()):
        window._quiz_trend_group_combo.setCurrentIndex(index)
        # Every group here has exactly one completed attempt, so a mixed
        # series (more than one point) would indicate two groups were
        # combined.
        assert window._quiz_chart._data is not None
        seen_point_counts.add(len(window._quiz_chart._data.points))
    assert seen_point_counts == {1}
    window.close()


def test_quiz_history_double_click_opens_review_dialog(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _, _, _, attempt_id, _ = _seed_rich_material(connection, tmp_path)

    opened: list[bool] = []
    monkeypatch.setattr(QuizReviewDialog, "exec", lambda self: opened.append(True))

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    assert window._quiz_history_list.count() == 1
    window._on_quiz_history_double_clicked(window._quiz_history_list.item(0))
    assert opened
    window.close()


def test_jump_to_cue_selects_the_right_row_in_player(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_id, cues = _make_material_with_cues(connection, tmp_path)

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    window._open_material(material_id, cues[1].id)
    assert window._child_window is not None
    assert window._child_window._cue_list.currentRow() == 1
    window._child_window.close()
    window.close()


def test_shadowing_practice_initial_cue_id_selects_matching_cue(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    material_id, cues = _make_material_with_cues(connection, tmp_path)

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    window._open_shadowing(material_id, cues[1].id)
    assert window._child_window is not None
    assert window._child_window._cue_index == 1
    window._child_window.close()
    window.close()
