from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox

from listentrace.application.services import loop_grace_service
from listentrace.application.services import practice_session_service as svc
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog


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


def test_save_and_continue_does_not_advance_when_stage1_completion_fails(qapp, conn, tmp_path, monkeypatch):
    """Final Pre-HG2 corrective #4 (P0): `complete_stage()` failing must never
    be silently swallowed and advanced past -- that discarded the domain
    validation contract and let a learner "complete" a session none of whose
    stages were actually resolved."""
    question_calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: question_calls.append(1) or QMessageBox.StandardButton.Yes)
    window, _, session_id = _open_guided_window(conn, tmp_path)

    # Stage 1 left entirely empty -- stage1_can_complete() requires at least
    # one non-whitespace response.
    window._on_save_and_continue_clicked()

    assert window._current_stage == "global_comprehension"
    assert window._stack.currentIndex() == 0
    state = svc.load_session_state(conn, session_id)
    assert state.stage_progress["global_comprehension"].status != "completed"
    assert window._status_label.text() != ""
    assert question_calls == [], "must not have navigated far enough to trigger the Stage 3 reveal confirmation"
    window.close()


def test_stale_status_banner_clears_on_legal_stage_advance(qapp, conn, tmp_path, monkeypatch):
    """Player/M13 Notebook Study Desk pass, spec §15: a validation error banner
    left over from a failed attempt must not still be visible after the
    learner supplies valid evidence and legally advances."""
    window, _, _ = _open_guided_window(conn, tmp_path)

    # Stage 1 left empty -- fails, banner is set.
    window._on_save_and_continue_clicked()
    assert window._status_label.text() != ""

    # Now supply valid data and legally advance.
    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()

    assert window._current_stage == "keyword_capture"
    assert window._status_label.text() == ""
    window.close()


def test_save_and_continue_does_not_advance_when_stage2_completion_fails(qapp, conn, tmp_path, monkeypatch):
    question_calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: question_calls.append(1) or QMessageBox.StandardButton.Yes)
    window, _, session_id = _open_guided_window(conn, tmp_path)

    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage2
    assert window._current_stage == "keyword_capture"

    # No captures added -- stage2_can_complete() requires at least one.
    window._on_save_and_continue_clicked()

    assert window._current_stage == "keyword_capture"
    assert window._stack.currentIndex() == 1
    state = svc.load_session_state(conn, session_id)
    assert state.stage_progress["keyword_capture"].status != "completed"
    assert state.session.transcript_revealed_at is None, "transcript must not be revealed as a side effect of a failed advance"
    assert question_calls == [], "must not have reached the Stage 3 reveal confirmation"
    window.close()


def test_save_and_continue_does_not_advance_when_stage3_completion_fails(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window, _, session_id = _open_guided_window(conn, tmp_path)

    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage2
    window._capture_type_combo.setCurrentIndex(0)
    window._capture_text_edit.setText("bonjour")
    window._on_add_capture_clicked()
    window._on_save_and_continue_clicked()  # -> stage3 (reveal confirmed)
    assert window._current_stage == "transcript_diagnosis"

    # No diagnosis evidence recorded and no explicit "No Notable Difficulty"
    # outcome -- stage3_can_complete() requires one or the other.
    window._on_save_and_continue_clicked()

    assert window._current_stage == "transcript_diagnosis"
    assert window._stack.currentIndex() == 2
    state = svc.load_session_state(conn, session_id)
    assert state.stage_progress["transcript_diagnosis"].status != "completed"
    window.close()


def test_save_and_continue_does_not_advance_when_stage4_has_unresolved_cues(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window, _, session_id = _open_guided_window(conn, tmp_path)

    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage2
    window._capture_type_combo.setCurrentIndex(0)
    window._capture_text_edit.setText("bonjour")
    window._on_add_capture_clicked()
    window._on_save_and_continue_clicked()  # -> stage3
    window._on_no_difficulty_clicked()
    window._on_save_and_continue_clicked()  # -> stage4
    assert window._current_stage == "shadowing"

    # No cue marked practiced or skipped -- stage4_can_complete() requires
    # every timed cue resolved (this material has 2 cues).
    window._on_save_and_continue_clicked()

    assert window._current_stage == "shadowing"
    assert window._stack.currentIndex() == 3
    state = svc.load_session_state(conn, session_id)
    assert state.stage_progress["shadowing"].status != "completed"
    window.close()


def test_save_and_continue_valid_flow_reaches_complete_session(qapp, conn, tmp_path, monkeypatch):
    """The counterpart to the four failure-path tests above: a fully legal
    Stage 1 -> 5 walk must still enable Complete Session end to end."""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    window, _, session_id = _open_guided_window(conn, tmp_path)

    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage2
    window._capture_type_combo.setCurrentIndex(0)
    window._capture_text_edit.setText("bonjour")
    window._on_add_capture_clicked()
    window._on_save_and_continue_clicked()  # -> stage3
    window._on_no_difficulty_clicked()
    window._on_save_and_continue_clicked()  # -> stage4
    window._on_skip_remaining_shadowing_clicked()
    window._on_save_and_continue_clicked()  # -> stage5
    assert window._current_stage == "final_summary"

    window._final_summary_edit.setPlainText("Short summary of what I understood.")
    window._on_save_and_continue_clicked()

    state = svc.load_session_state(conn, session_id)
    for stage_key in (
        "global_comprehension",
        "keyword_capture",
        "transcript_diagnosis",
        "shadowing",
        "final_summary",
    ):
        assert state.stage_progress[stage_key].status in ("completed", "skipped"), stage_key
    assert window._complete_button.isEnabled() is True

    window._on_complete_session_clicked()
    state = svc.load_session_state(conn, session_id)
    assert state.session.status == "completed"
    window.close()


def test_transcript_reveal_requires_confirmation_and_locks_stage1_2(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    window, _, session_id = _open_guided_window(conn, tmp_path)
    assert window._stage1_lock_hint.isHidden() is True
    assert window._stage2_lock_hint.isHidden() is True

    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage 2
    window._on_skip_stage_clicked()  # -> stage 3, triggers reveal confirmation (auto-Yes)

    assert window._current_stage == "transcript_diagnosis"
    session = svc.get_session(conn, session_id)
    assert session.transcript_revealed_at is not None
    assert window._diagnosis_cue_list.count() == 2

    # Stage 1 is now read-only, and the UI now explains why (M12.3 regression:
    # previously the controls just went grey with no on-screen explanation).
    assert window._stage1_edits["where"].isReadOnly() is True
    assert window._stage1_lock_hint.isHidden() is False
    assert window._stage2_lock_hint.isHidden() is False
    window.close()


def test_reveal_confirmation_declined_stays_on_stage2(qapp, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    window, _, session_id = _open_guided_window(conn, tmp_path)
    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage 2
    window._capture_type_combo.setCurrentIndex(0)
    window._capture_text_edit.setText("bonjour")
    window._on_add_capture_clicked()
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


def test_stage5_summary_save_and_continue_enables_complete_button(qapp, conn, tmp_path, monkeypatch):
    """M12 Round 4 Batch A: reproduces the human-QA report that `Complete Session`
    stays disabled after Stage 5's summary is filled in. Walks the real UI path
    (not `svc.*` shortcuts) end to end to determine whether this is a UI-wiring
    defect or a discoverability gap: typing the summary alone must not enable
    Complete (that would be a *different* bug -- silent auto-completion), but
    clicking the documented "Save and Continue" action on Stage 5 must."""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window, _, session_id = _open_guided_window(conn, tmp_path)

    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage2
    window._on_skip_stage_clicked()  # -> stage3 (triggers reveal confirmation, auto-Yes)
    window._on_skip_stage_clicked()  # -> stage4
    window._on_skip_stage_clicked()  # -> stage5
    assert window._current_stage == "final_summary"
    assert window._complete_button.isEnabled() is False

    window._final_summary_edit.setPlainText("Short summary of what I understood.")
    assert window._complete_button.isEnabled() is False, (
        "Typing the summary alone must not silently satisfy completion -- "
        "only an explicit save action should."
    )

    window._on_save_and_continue_clicked()  # the only documented action that resolves stage 5
    state = svc.load_session_state(conn, session_id)
    assert state.stage_progress["final_summary"].status == "completed"
    assert window._complete_button.isEnabled() is True, (
        "Complete Session must become enabled once every stage is resolved via "
        "the documented UI action."
    )
    window.close()


def test_complete_button_disabled_reason_is_visible_and_accurate(qapp, conn, tmp_path, monkeypatch):
    """M12 Round 3 Completion/Explainability Contract: a disabled `Complete
    Session` must show an inspectable reason, not just render grey.

    M13 corrective pass (#8): the footer was compressed from a loud
    full-checklist inline string into a concise unresolved-stage summary —
    the reason must still be visible and accurate, just quieter."""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window, _, _ = _open_guided_window(conn, tmp_path)

    assert "Global Comprehension" in window._completion_status_label.text()
    assert "Final Recall" in window._completion_status_label.text()

    window._stage1_edits["where"].setPlainText("A cafe")
    window._on_save_and_continue_clicked()  # -> stage2
    window._on_skip_stage_clicked()  # -> stage3
    window._on_skip_stage_clicked()  # -> stage4
    window._on_skip_stage_clicked()  # -> stage5

    assert "Final Recall" in window._completion_status_label.text()
    assert "Global Comprehension" not in window._completion_status_label.text()

    window._final_summary_edit.setPlainText("Short summary.")
    window._on_save_and_continue_clicked()
    assert window._completion_status_label.text() == "All stages resolved — ready to complete."
    window.close()


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


def test_loop_settings_button_opens_the_shared_dialog_from_either_stage(qapp, conn, tmp_path):
    window, material_id, _ = _open_guided_window(conn, tmp_path)

    window._on_open_loop_settings()
    assert isinstance(window._loop_settings_dialog, MaterialLoopSettingsDialog)
    first = window._loop_settings_dialog
    window._diagnosis_loop_settings_button.click()
    window._shadowing_loop_settings_button.click()
    assert window._loop_settings_dialog is first, "one shared dialog regardless of which stage opened it"
    window.close()


def test_material_override_changed_updates_this_windows_live_session_grace(qapp, conn, tmp_path):
    window, material_id, _ = _open_guided_window(conn, tmp_path)

    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    loop_grace_change_bus.material_override_changed.emit(material_id)

    assert window._player_session._loop_end_grace_ms == 90
    window.close()
