from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QScrollArea, QSplitter

from listentrace.application.services import practice_session_service as svc
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow, RuledTextEdit, StageStepper


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "guided_m13.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _open_guided_window(conn, tmp_path):
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nBonjour tout le monde\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nSecond cue\n",
        encoding="utf-8",
    )
    result = import_material(conn, media_path, srt, "Guided Lesson M13")
    load_result = load_material_for_player(conn, result.material_id)
    session = svc.start_session(conn, result.material_id)
    window = GuidedSessionWindow(conn, load_result, session.id, tmp_path / "recordings")
    return window, result.material_id, session.id


def test_guided_session_m13_stepper_and_topology(qapp, conn, tmp_path):
    window, _, _ = _open_guided_window(conn, tmp_path)
    window.show()

    # 1. Top Bar & Stepper Verification
    assert hasattr(window, "_stage_stepper")
    assert isinstance(window._stage_stepper, StageStepper)
    assert len(window._stage_stepper._step_buttons) == 5
    assert window._stage_stepper._step_badges["global_comprehension"].text() == "1"

    # Current stage is enabled; future unreached stages are disabled (mouse AND
    # keyboard cannot jump ahead of legally reached stages).
    assert window._stage_stepper._step_buttons["global_comprehension"].isEnabled()
    for future_key in ("transcript_diagnosis", "shadowing", "final_summary"):
        assert not window._stage_stepper._step_buttons[future_key].isEnabled()

    # Stepper items are keyboard-focusable (StrongFocus), not mouse-only.
    assert (
        window._stage_stepper._step_buttons["global_comprehension"].focusPolicy()
        == Qt.FocusPolicy.StrongFocus
    )

    # 2. Stage 1 Canvas
    stage1_widget = window._stack.widget(0)
    assert isinstance(stage1_widget, QScrollArea)
    assert stage1_widget.property("surface") == "paper"

    # 3. Stage 3 Splitter Architecture
    stage3_widget = window._stack.widget(2)
    assert isinstance(stage3_widget, QSplitter)
    assert stage3_widget.orientation() == Qt.Orientation.Horizontal
    assert stage3_widget.count() == 2

    # 4. Stage 4 Studio Structure
    stage4_widget = window._stack.widget(3)
    assert isinstance(stage4_widget, QScrollArea)
    assert hasattr(window, "_recording_panel")

    # 5. Stage 5 Notebook Surface
    stage5_widget = window._stack.widget(4)
    assert stage5_widget.property("surface") == "paper"
    assert stage5_widget.property("role") == "notebook_page"
    assert hasattr(window, "_final_summary_edit")

    # 6. Action Hierarchy
    assert window._continue_button.property("role") == "primary"
    assert window._complete_button.property("role") == "success"
    assert window._abandon_button.property("role") == "danger"
    assert window._back_button.property("role") == "quiet"

    window.close()


def test_guided_session_m13_stepper_updates_on_stage_advance(qapp, conn, tmp_path):
    window, _, _ = _open_guided_window(conn, tmp_path)
    window.show()

    # Fill Stage 1 and advance
    window._stage1_edits["who_is_speaking"].setPlainText("Speaker A")
    window._on_save_and_continue_clicked()

    assert window._current_stage == "keyword_capture"
    assert window._stack.currentIndex() == 1
    # Stage 1 should show completed checkmark
    assert window._stage_stepper._step_badges["global_comprehension"].text() == "✓"
    # Stage 2 should show active step 2
    assert window._stage_stepper._step_badges["keyword_capture"].text() == "2"

    window.close()


def test_guided_session_m13_stepper_blocks_illegal_forward_jump(qapp, conn, tmp_path):
    window, _, _ = _open_guided_window(conn, tmp_path)
    window.show()

    # Stage 3/4/5 are unreached from Stage 1: disabled buttons cannot emit
    # clicked, so no click can reach _on_stepper_stage_clicked for them.
    for future_key in ("transcript_diagnosis", "shadowing", "final_summary"):
        btn = window._stage_stepper._step_buttons[future_key]
        assert not btn.isEnabled()
        btn.click()  # a disabled QPushButton.click() is a no-op

    assert window._current_stage == "global_comprehension"
    assert window._stack.currentIndex() == 0

    window.close()


def test_guided_session_m13_stepper_keyboard_activation(qapp, conn, tmp_path):
    window, _, _ = _open_guided_window(conn, tmp_path)
    window.show()

    window._stage1_edits["who_is_speaking"].setPlainText("Speaker A")
    window._on_save_and_continue_clicked()
    assert window._current_stage == "keyword_capture"

    # Stage 1 is now completed/reached and enabled; activate it via keyboard
    # (Space) rather than a mouse click.
    stage1_btn = window._stage_stepper._step_buttons["global_comprehension"]
    assert stage1_btn.isEnabled()
    stage1_btn.setFocus()
    QTest.keyClick(stage1_btn, Qt.Key.Key_Space)

    assert window._current_stage == "global_comprehension"

    window.close()


def test_guided_session_m13_stepper_read_only_disables_all(qapp, conn, tmp_path):
    window, _, session_id = _open_guided_window(conn, tmp_path)
    window.show()

    svc.abandon_session(conn, session_id)
    window._refresh_state()

    for btn in window._stage_stepper._step_buttons.values():
        assert not btn.isEnabled()

    window.close()


def test_ruled_text_edit_line_phase_stays_anchored_to_the_document_at_any_scroll_offset():
    """Final Pre-HG2 corrective pass #12: the ruled-line pattern must be
    anchored to the document, not the viewport, so lines don't drift out of
    alignment with text baselines once the scroll offset isn't an exact
    multiple of the line spacing."""
    spacing = 28

    # No scroll: first line at its original fixed offset.
    assert RuledTextEdit._ruled_line_phase(spacing, 0) == spacing - 1

    # Scrolling by exactly one line spacing must reproduce the same phase.
    assert RuledTextEdit._ruled_line_phase(spacing, spacing) == RuledTextEdit._ruled_line_phase(spacing, 0)

    # An arbitrary non-multiple scroll offset must shift the phase by the
    # same (negated, wrapped) amount -- not stay fixed at the un-scrolled value.
    for offset in (1, 13, 27, 41, 100):
        phase = RuledTextEdit._ruled_line_phase(spacing, offset)
        assert 0 <= phase < spacing
        assert (phase + offset - (spacing - 1)) % spacing == 0
