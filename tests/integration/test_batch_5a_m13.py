from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QRadioButton, QScrollArea, QSplitter

from listentrace.application.services import (
    practice_session_service,
    quick_practice_service,
    quiz_service,
)
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.domain.enums.quick_practice_status import QuickPracticeStatus
from listentrace.domain.enums.quiz_mode import QuizMode
from listentrace.domain.enums.stage_key import StageKey
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow, StageStepper
from listentrace.ui.windows.learning_history_window import LearningHistoryWindow
from listentrace.ui.windows.main_window import MainWindow
from listentrace.ui.windows.player_window import PlayerWindow
from listentrace.ui.windows.quick_practice_window import QuickPracticeWindow
from listentrace.ui.windows.quiz_history_dialog import QuizHistoryDialog
from listentrace.ui.windows.quiz_review_dialog import QuizReviewDialog
from listentrace.ui.windows.quiz_window import QuizOptionCard, QuizWindow
from listentrace.ui.windows.session_history_dialog import SessionHistoryDialog
from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "batch5a_m13.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=3, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _setup_material(conn, tmp_path):
    media_path = tmp_path / "integration_lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "integration_lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nPremier element de test\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nDeuxieme phrase structuree\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nTroisieme segment d analyse\n",
        encoding="utf-8",
    )
    return import_material(conn, media_path, srt, "Batch 5A Integration Lesson")


def test_whole_product_surface_inventory(qapp, conn, tmp_path):
    """Verifies all major and dialog surfaces exist and instantiate under M13."""
    res = _setup_material(conn, tmp_path)
    load_result = load_material_for_player(conn, res.material_id)
    rec_dir = tmp_path / "recordings"

    # 1. MainWindow
    main_win = MainWindow(conn, tmp_path / "app.db", rec_dir)
    assert main_win.property("surface") == "workspace"

    # 2. PlayerWindow
    player_win = PlayerWindow(load_result, conn)
    assert player_win.property("surface") == "cinema"

    # 3. GuidedSessionWindow
    session = practice_session_service.start_session(conn, res.material_id)
    guided_win = GuidedSessionWindow(conn, load_result, session.id, rec_dir)
    assert guided_win.property("surface") == "paper"
    assert isinstance(guided_win._stage_stepper, StageStepper)

    # 4. QuizWindow
    attempt = quiz_service.create_material_quiz(conn, res.material_id, requested_count=2, seed=1)
    quiz_win = QuizWindow(conn, load_result, attempt.id)
    assert quiz_win.property("surface") == "paper"

    # 5. QuizReviewDialog
    quiz_service.submit_quiz(conn, attempt.id)
    review_dlg = QuizReviewDialog(conn, attempt.id)
    assert review_dlg.property("surface") == "paper"

    # 6. QuickPracticeWindow
    qp_session = quick_practice_service.start_selected_session(conn, res.material_id, [load_result.cues[0].id])
    qp_win = QuickPracticeWindow(conn, load_result, qp_session.id, rec_dir)
    assert qp_win.property("surface") == "paper"

    # 7. ShadowingPracticeWindow
    shadow_win = ShadowingPracticeWindow(conn, load_result, rec_dir)
    assert hasattr(shadow_win, "_recording_panel")

    # 8. LearningHistoryWindow
    history_win = LearningHistoryWindow(conn, rec_dir, initial_material_id=res.material_id)
    assert history_win.property("surface") == "paper"

    # 9. SessionHistoryDialog & QuizHistoryDialog
    sess_dlg = SessionHistoryDialog(conn, res.material_id, load_result.material.title)
    assert sess_dlg.property("surface") == "paper"
    quiz_dlg = QuizHistoryDialog(conn, res.material_id, load_result.material.title)
    assert quiz_dlg.property("surface") == "paper"

    for w in (main_win, player_win, guided_win, quiz_win, review_dlg, qp_win, shadow_win, history_win, sess_dlg, quiz_dlg):
        w.close()


def test_stage_stepper_and_stage2_scope_fidelity(qapp, conn, tmp_path):
    """Carry-forward check: StageStepper navigation and Stage 2 capture fidelity."""
    res = _setup_material(conn, tmp_path)
    load_result = load_material_for_player(conn, res.material_id)
    rec_dir = tmp_path / "recordings"

    session = practice_session_service.start_session(conn, res.material_id)
    guided_win = GuidedSessionWindow(conn, load_result, session.id, rec_dir)
    guided_win.show()

    # Stage 1 -> Stage 2 transition
    guided_win._on_save_and_continue_clicked()
    assert guided_win._current_stage == StageKey.KEYWORD_CAPTURE.value

    # Stage 2 Add, Move, Reorder
    guided_win._capture_text_edit.setText("premier")
    guided_win._on_add_capture_clicked()
    guided_win._capture_text_edit.setText("deuxieme")
    guided_win._on_add_capture_clicked()
    assert guided_win._capture_list.count() == 2

    captures = practice_session_service.list_keyword_captures(conn, session.id)
    assert len(captures) == 2
    assert captures[0].text == "premier"
    assert captures[1].text == "deuxieme"

    guided_win.close()


def test_quick_practice_replacement_regression_retained(qapp, conn, tmp_path):
    """Carry-forward check: Quick practice window replacement cleanly abandons prior multi-cue session with evidence."""
    res = _setup_material(conn, tmp_path)
    load_result = load_material_for_player(conn, res.material_id)
    player = PlayerWindow(load_result, conn)

    # Open multi-cue quick practice (cues 0 & 1)
    player._open_quick_practice([load_result.cues[0].id, load_result.cues[1].id])
    first_window = player._quick_practice_window
    assert isinstance(first_window, QuickPracticeWindow)

    # Complete 1 cue in first_window so it has evidence and is abandoned rather than discarded
    first_window._recall_radio_buttons["understood"].setChecked(True)
    first_window._on_step_action_clicked()
    first_window._on_step_action_clicked()
    first_window._on_step_action_clicked() # completes item 0, moves to item 1

    player._open_quick_practice([load_result.cues[2].id])
    second_window = player._quick_practice_window
    assert isinstance(second_window, QuickPracticeWindow)
    assert second_window is not first_window
    assert first_window.isVisible() is False

    state = quick_practice_service.load_session_state(conn, first_window._session_id)
    assert state.session.status == QuickPracticeStatus.ABANDONED.value

    player.close()
    second_window.close()


def test_responsive_resize_stability(qapp, conn, tmp_path):
    """Audits representative window sizes: 800x600, 980x640, 1280x720, 1600x900."""
    res = _setup_material(conn, tmp_path)
    load_result = load_material_for_player(conn, res.material_id)
    rec_dir = tmp_path / "recordings"

    windows = [
        MainWindow(conn, tmp_path / "app.db", rec_dir),
        PlayerWindow(load_result, conn),
        GuidedSessionWindow(conn, load_result, practice_session_service.start_session(conn, res.material_id).id, rec_dir),
        LearningHistoryWindow(conn, rec_dir, initial_material_id=res.material_id),
    ]

    sizes = [(880, 600), (980, 640), (1280, 720), (1600, 900)]
    for win in windows:
        win.show()
        for w, h in sizes:
            win.resize(w, h)
            qapp.processEvents()
            assert win.width() >= 800
            assert win.height() >= 550
        win.close()
