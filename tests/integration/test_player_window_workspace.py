from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox

from listentrace.application.services import annotation_service, cue_note_service
from listentrace.application.services import label_preference_service
from listentrace.application.services import saved_language_item_service as item_service
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.player_window import PlayerWindow


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _open_window(conn, tmp_path, cue_text="Bonjour tout le monde"):
    media = tmp_path / "lesson.wav"
    _make_wav(media)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        f"1\n00:00:00,000 --> 00:00:01,000\n{cue_text}\n\n2\n00:00:01,000 --> 00:00:02,000\nSecond cue\n",
        encoding="utf-8",
    )
    result = import_material(conn, media, srt, "Workspace Lesson")
    load_result = load_material_for_player(conn, result.material_id)
    return PlayerWindow(load_result, conn), result.material_id


def _select_range(window, start, end):
    cursor = window._editing_transcript_view.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    window._editing_transcript_view.setTextCursor(cursor)


def test_editing_cue_independent_of_active_playback_cue(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)

    window._cue_list.setCurrentRow(0)
    assert window._editing_cue_index == 0

    # Simulate playback moving into the second cue's time range.
    window._on_position_changed(1500)
    assert window._session.active_cue_index == 1
    # The editing cue must not have been stolen by playback progress.
    assert window._editing_cue_index == 0

    window.close()


def test_selecting_cue_populates_workspace_from_existing_data(qapp, conn, tmp_path):
    window, material_id = _open_window(conn, tmp_path)
    cue = window._session.cues[0]

    annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    cue_note_service.save_cue_note(conn, cue.id, "a note")
    item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)

    window._cue_list.setCurrentRow(0)

    assert window._annotation_list.count() == 1
    assert window._cue_note_edit.toPlainText() == "a note"
    assert window._saved_items_list.count() == 1

    window.close()


def test_save_single_label_annotation_via_ui(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)

    window._label_checkboxes["keyword"].setChecked(True)
    window._on_save_annotation_clicked()

    assert window._workspace_status_label.text() == ""
    assert window._annotation_list.count() == 1
    assert window._annotation_list.item(0).text().startswith("[keyword]")

    window.close()


def test_save_multiple_labels_atomically_via_ui(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)

    window._label_checkboxes["keyword"].setChecked(True)
    window._label_checkboxes["unknown_word_or_chunk"].setChecked(True)
    window._on_save_annotation_clicked()

    assert window._annotation_list.count() == 2

    window.close()


def test_misheard_without_heard_as_shows_error_and_creates_nothing(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)

    window._label_checkboxes["misheard"].setChecked(True)
    window._on_save_annotation_clicked()

    assert "heard_as" in window._workspace_status_label.text()
    assert window._annotation_list.count() == 0

    window.close()


def test_edit_and_delete_annotation_via_ui(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)
    window._label_checkboxes["keyword"].setChecked(True)
    window._on_save_annotation_clicked()

    window._annotation_list.setCurrentRow(0)
    annotation_id = window._editing_annotation_id
    assert annotation_id is not None

    window._annotation_note_edit.setText("edited note")
    window._on_update_annotation_clicked()
    annotations = annotation_service.list_annotations_for_cue(conn, window._session.cues[0].id)
    assert annotations[0].note == "edited note"

    window._annotation_list.setCurrentRow(0)
    annotation_service.delete_annotation(conn, window._editing_annotation_id)
    window._refresh_editing_cue_panels()
    assert window._annotation_list.count() == 0

    window.close()


def test_cue_note_edit_via_ui(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)

    window._cue_note_edit.setPlainText("first note")
    window._on_save_note_clicked()
    assert cue_note_service.get_cue_note(conn, window._session.cues[0].id).note_text == "first note"

    window._cue_note_edit.setPlainText("   ")
    window._on_save_note_clicked()
    assert cue_note_service.get_cue_note(conn, window._session.cues[0].id) is None

    window.close()


def test_save_and_edit_language_item_via_ui(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)

    window._item_meaning_edit.setText("hello")
    window._on_save_item_clicked()
    assert window._saved_items_list.count() == 1

    window._saved_items_list.setCurrentRow(0)
    item_id = window._editing_item_id
    window._item_meaning_edit.setText("hello (greeting)")
    window._on_update_item_clicked()

    items = item_service.list_saved_items_for_cue(conn, window._session.cues[0].id)
    assert items[0].meaning == "hello (greeting)"

    window.close()


def test_duplicate_saved_item_warning_flow_confirms_and_creates(qapp, conn, tmp_path, monkeypatch):
    window, material_id = _open_window(conn, tmp_path)
    cue1 = window._session.cues[0]

    # Pre-existing item with the same normalized text in a *different* cue/material context.
    from listentrace.domain.models.material import Material
    from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
    from listentrace.infrastructure.db.repository import (
        get_cues_for_track,
        insert_material,
        insert_subtitle_track,
    )

    other_material_id = insert_material(conn, Material(title="Other", media_path="other.mp4"))
    other_track = SubtitleTrack(
        material_id=other_material_id,
        format="srt",
        source_path="other.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour a tous")],
    )
    other_track_id = insert_subtitle_track(conn, other_track)
    other_cue = get_cues_for_track(conn, other_track_id)[0]
    item_service.save_language_item(conn, other_material_id, other_cue.id, "word", 0, 7)

    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)  # "Bonjour" in this window's first cue

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._on_save_item_clicked()

    assert window._saved_items_list.count() == 1

    window.close()


def test_hidden_transcript_does_not_expose_cue_text(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path, cue_text="Secret transcript content")
    window._cue_list.setCurrentRow(0)
    assert "Secret transcript content" in window._editing_transcript_view.toPlainText()

    window._on_toggle_transcript()
    assert window._session.transcript_visible is False
    assert window._editing_transcript_view.toPlainText() == ""
    assert window._workspace_panel.isVisible() is False

    window._on_toggle_transcript()
    assert window._session.transcript_visible is True
    # Re-showing must not silently lose the ability to repopulate on reselect.
    window._refresh_editing_cue_panels()
    assert "Secret transcript content" in window._editing_transcript_view.toPlainText()

    window.close()


def test_label_color_update_changes_presentation_not_semantics(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)
    window._label_checkboxes["keyword"].setChecked(True)
    window._on_save_annotation_clicked()

    label_preference_service.update_label_color(conn, "keyword", "#123456")
    # Must not raise, and the annotation's label/text must be unaffected.
    window._refresh_editing_cue_panels()

    annotations = annotation_service.list_annotations_for_cue(conn, window._session.cues[0].id)
    assert annotations[0].label_key == "keyword"
    assert annotations[0].selected_text == "Bonjour"

    window.close()


def test_m3_controls_still_work_alongside_workspace(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)

    # Loop-cue selection and workspace editing-cue selection both use the cue list,
    # but must not interfere with each other.
    window._cue_list.item(0).setSelected(True)
    window._cue_list.item(1).setSelected(True)
    window._on_loop_range_clicked()
    assert window._session.loop_mode is not None

    window.close()
