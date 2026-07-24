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
    item_service.save_language_item(conn, cue.id, "word", 0, 7)

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


def test_edit_annotation_can_change_label_and_range_via_ui(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)
    window._label_checkboxes["keyword"].setChecked(True)
    window._on_save_annotation_clicked()

    window._annotation_list.setCurrentRow(0)
    assert window._editing_annotation_id is not None

    # Change both the label and the range, then Update.
    window._label_checkboxes["keyword"].setChecked(False)
    window._label_checkboxes["unknown_word_or_chunk"].setChecked(True)
    _select_range(window, 8, 12)  # "tout"
    window._on_update_annotation_clicked()

    assert window._workspace_status_label.text() == ""
    annotations = annotation_service.list_annotations_for_cue(conn, window._session.cues[0].id)
    assert len(annotations) == 1
    assert annotations[0].label_key == "unknown_word_or_chunk"
    assert annotations[0].selected_text == "tout"

    window.close()


def test_update_annotation_requires_exactly_one_checked_label(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)
    window._label_checkboxes["keyword"].setChecked(True)
    window._on_save_annotation_clicked()

    window._annotation_list.setCurrentRow(0)
    window._label_checkboxes["unknown_word_or_chunk"].setChecked(True)  # now two checked
    window._on_update_annotation_clicked()

    assert "exactly one label" in window._workspace_status_label.text()
    # nothing should have changed
    annotations = annotation_service.list_annotations_for_cue(conn, window._session.cues[0].id)
    assert len(annotations) == 1
    assert annotations[0].label_key == "keyword"

    window.close()


def test_edit_saved_item_type_via_ui_with_source_locked(qapp, conn, tmp_path):
    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)
    window._item_type_combo.setCurrentIndex(window._item_type_combo.findData("word"))
    window._on_save_item_clicked()
    assert window._saved_items_list.count() == 1

    window._saved_items_list.setCurrentRow(0)
    assert window._editing_item_id is not None

    # Change the type (allowed) while the transcript selection moves elsewhere —
    # the update must not re-derive a new source range from that selection.
    window._item_type_combo.setCurrentIndex(window._item_type_combo.findData("phrase"))
    _select_range(window, 8, 12)  # "tout" — must be ignored by update
    window._on_update_item_clicked()

    assert window._workspace_status_label.text() == ""
    items = item_service.list_saved_items_for_cue(conn, window._session.cues[0].id)
    assert items[0].item_type == "phrase"
    assert items[0].text == "Bonjour"  # source text unchanged despite the later selection
    assert (items[0].selection_start, items[0].selection_end) == (0, 7)

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
    item_service.save_language_item(conn, other_cue.id, "word", 0, 7)

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


def test_annotation_list_shows_a_color_badge_matching_the_label_color(qapp, conn, tmp_path):
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QColor

    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)
    window._label_checkboxes["keyword"].setChecked(True)
    window._on_save_annotation_clicked()

    item = window._annotation_list.item(0)
    assert not item.icon().isNull()
    # The label text itself must still be visible — color is not the only cue.
    assert item.text().startswith("[keyword]")

    default_color = label_preference_service.get_label_preferences(conn)["keyword"]
    badge_pixel = item.icon().pixmap(QSize(12, 12)).toImage().pixelColor(0, 0)
    assert badge_pixel == QColor(default_color)

    # Changing the global color must refresh the badge (and the transcript
    # highlight) without changing which annotation/label exists.
    label_preference_service.update_label_color(conn, "keyword", "#00FF00")
    window._refresh_editing_cue_panels()

    updated_item = window._annotation_list.item(0)
    updated_pixel = updated_item.icon().pixmap(QSize(12, 12)).toImage().pixelColor(0, 0)
    assert updated_pixel == QColor("#00FF00")
    assert updated_item.text().startswith("[keyword]")

    window.close()


def test_overlapping_annotations_each_show_their_own_badge_and_stay_selectable(qapp, conn, tmp_path):
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QColor

    window, _ = _open_window(conn, tmp_path)
    window._cue_list.setCurrentRow(0)
    _select_range(window, 0, 7)
    window._label_checkboxes["keyword"].setChecked(True)
    window._label_checkboxes["unknown_word_or_chunk"].setChecked(True)
    window._on_save_annotation_clicked()

    assert window._annotation_list.count() == 2
    colors = label_preference_service.get_label_preferences(conn)

    row0_pixel = window._annotation_list.item(0).icon().pixmap(QSize(12, 12)).toImage().pixelColor(0, 0)
    row1_pixel = window._annotation_list.item(1).icon().pixmap(QSize(12, 12)).toImage().pixelColor(0, 0)
    row_colors = {row0_pixel.name(), row1_pixel.name()}
    expected_colors = {QColor(colors["keyword"]).name(), QColor(colors["unknown_word_or_chunk"]).name()}
    assert row_colors == expected_colors

    # Each row must remain independently selectable.
    window._annotation_list.setCurrentRow(0)
    first_id = window._editing_annotation_id
    window._annotation_list.setCurrentRow(1)
    second_id = window._editing_annotation_id
    assert first_id != second_id

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


def test_non_bmp_selection_round_trips_through_real_qt_widget(qapp, conn, tmp_path):
    emoji_text = "hi \U0001F600 there"  # emoji is non-BMP: 2 UTF-16 units, 1 code point
    window, _ = _open_window(conn, tmp_path, cue_text=emoji_text)
    window._cue_list.setCurrentRow(0)

    assert window._editing_transcript_view.toPlainText() == emoji_text

    # Select "there" using the real QTextDocument search, so this exercises Qt's own
    # UTF-16 cursor positions rather than positions we computed ourselves.
    found_cursor = window._editing_transcript_view.document().find("there")
    assert not found_cursor.isNull()
    window._editing_transcript_view.setTextCursor(found_cursor)

    start, end = window._current_selection_range(emoji_text)
    assert emoji_text[start:end] == "there"
    assert (start, end) == (5, 10)  # codepoint indices: "hi " (3) + emoji (1) + " " (1)

    window._label_checkboxes["keyword"].setChecked(True)
    window._on_save_annotation_clicked()
    assert window._workspace_status_label.text() == ""

    annotations = annotation_service.list_annotations_for_cue(conn, window._session.cues[0].id)
    assert annotations[0].selected_text == "there"
    assert (annotations[0].selection_start, annotations[0].selection_end) == (5, 10)

    # Selecting the annotation must restore the correct Qt selection despite the
    # preceding non-BMP character.
    window._annotation_list.setCurrentRow(0)
    restored = window._editing_transcript_view.textCursor()
    assert restored.selectedText() == "there"

    # Highlighting must not crash or misplace the highlight for non-BMP text.
    window._refresh_editing_cue_panels()

    window.close()


def test_non_bmp_character_inside_selection_round_trips(qapp, conn, tmp_path):
    emoji_text = "hi \U0001F600 there"
    window, _ = _open_window(conn, tmp_path, cue_text=emoji_text)
    window._cue_list.setCurrentRow(0)

    # Select from the start of the text through just after the emoji + following space,
    # i.e. a selection that *contains* the non-BMP character rather than starting after it.
    cursor = window._editing_transcript_view.textCursor()
    cursor.setPosition(0)
    # 5 character-steps: h, i, ' ', (the emoji as one step), ' ' -> lands right before "there".
    cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, 5)
    window._editing_transcript_view.setTextCursor(cursor)

    start, end = window._current_selection_range(emoji_text)
    assert emoji_text[start:end] == "hi \U0001F600 "

    window._label_checkboxes["unknown_word_or_chunk"].setChecked(True)
    window._on_save_annotation_clicked()
    assert window._workspace_status_label.text() == ""

    annotations = annotation_service.list_annotations_for_cue(conn, window._session.cues[0].id)
    assert annotations[0].selected_text == "hi \U0001F600 "

    window.close()
