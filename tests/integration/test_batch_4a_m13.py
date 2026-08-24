from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QRadioButton, QScrollArea

from listentrace.application.services import quick_practice_service, quiz_service
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.learning_history_window import LearningHistoryWindow
from listentrace.ui.windows.quick_practice_window import QuickPracticeWindow
from listentrace.ui.windows.quiz_review_dialog import QuizReviewDialog
from listentrace.ui.windows.quiz_window import QuizOptionCard, QuizWindow
from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "batch4a_m13.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _setup_material(conn, tmp_path):
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nBonjour tout le monde\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nDeuxieme phrase de test\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nTroisieme phrase\n",
        encoding="utf-8",
    )
    return import_material(conn, media_path, srt, "Batch 4A Lesson")


def test_quiz_window_m13_architecture(qapp, conn, tmp_path):
    res = _setup_material(conn, tmp_path)
    load_result = load_material_for_player(conn, res.material_id)
    attempt = quiz_service.create_material_quiz(conn, res.material_id, requested_count=2, seed=42)
    window = QuizWindow(conn, load_result, attempt.id)
    window.show()

    # 1. Canvas & Surface
    assert window.property("surface") == "paper"
    assert hasattr(window, "_question_label")
    assert hasattr(window, "_answer_stack")

    # 2. QuizOptionCard Composites
    choice_panel = window._answer_stack.widget(1)
    assert isinstance(choice_panel, QScrollArea)
    assert len(window._choice_cards) == 4
    for card in window._choice_cards:
        assert isinstance(card, QuizOptionCard)
        assert isinstance(card._radio, QRadioButton)

    # 3. Action Hierarchy
    assert window._submit_button.property("role") == "primary"
    assert window._abandon_button.property("role") == "danger"
    assert window._close_button.property("role") == "quiet"

    window.close()


def test_quiz_review_dialog_m13_architecture(qapp, conn, tmp_path):
    res = _setup_material(conn, tmp_path)
    attempt = quiz_service.create_material_quiz(conn, res.material_id, requested_count=2, seed=42)
    quiz_service.submit_quiz(conn, attempt.id)
    dialog = QuizReviewDialog(conn, attempt.id)
    dialog.show()

    assert dialog.property("surface") == "paper"
    assert hasattr(dialog, "_list")
    assert hasattr(dialog, "_detail_view")

    dialog.close()


def test_quick_practice_window_m13_architecture(qapp, conn, tmp_path):
    res = _setup_material(conn, tmp_path)
    load_result = load_material_for_player(conn, res.material_id)
    session = quick_practice_service.start_selected_session(conn, res.material_id, [load_result.cues[0].id])
    window = QuickPracticeWindow(conn, load_result, session.id, tmp_path / "recordings")
    window.show()

    assert window.property("surface") == "paper"
    assert hasattr(window, "_step_action_button")
    assert window._step_action_button.property("role") == "primary"
    assert hasattr(window, "_recording_panel")

    window.close()


def test_shadowing_practice_window_m13_architecture(qapp, conn, tmp_path):
    res = _setup_material(conn, tmp_path)
    load_result = load_material_for_player(conn, res.material_id)
    window = ShadowingPracticeWindow(conn, load_result, tmp_path / "recordings")
    window.show()

    assert hasattr(window, "_cue_label")
    assert hasattr(window, "_recording_panel")
    assert hasattr(window, "_delete_material_recordings_button")
    assert window._delete_material_recordings_button.property("role") == "danger"

    window.close()


def test_learning_history_window_m13_architecture(qapp, conn, tmp_path):
    window = LearningHistoryWindow(conn, tmp_path / "recordings")
    window.show()

    assert window.property("surface") == "paper"
    assert hasattr(window, "_tabs")
    assert window._tabs.count() == 7

    window.close()
