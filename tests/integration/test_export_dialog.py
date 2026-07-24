from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from listentrace.application.services import export_formatters, export_service
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_subtitle_track_for_material,
    insert_material,
    insert_subtitle_track,
)
from listentrace.ui.windows.export_dialog import ExportDialog
from listentrace.ui.windows.learning_history_window import LearningHistoryWindow
from listentrace.ui.windows.main_window import MainWindow


def _make_material_with_cues(conn, tmp_path, title="Lesson"):
    media_path = tmp_path / f"{title}.mp4"
    media_path.write_bytes(b"fake media bytes" * 10)
    subtitle_path = tmp_path / f"{title}.srt"
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")
    material_id = insert_material(conn, Material(title=title, media_path=str(media_path), language="fr"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path=str(subtitle_path),
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    insert_subtitle_track(conn, track)
    track_row = get_subtitle_track_for_material(conn, material_id)
    cues = get_cues_for_track(conn, track_row.id)
    return material_id, cues


def test_dialog_opens_and_generates_a_preview(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()

    assert dialog._bundle is not None
    assert len(dialog._bundle.materials) == 1
    assert dialog._save_markdown_button.isEnabled()
    dialog.close()


def test_preview_matches_a_direct_service_and_formatter_call(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()

    direct_bundle = export_service.build_export(
        connection,
        dialog._current_scope(),
        dialog._current_date_range(),
        dialog._selected_categories(),
        dialog._selected_privacy_fields(),
    )
    assert export_formatters.render_markdown(direct_bundle) == dialog._markdown_text
    assert export_formatters.render_json(direct_bundle) == dialog._json_text
    dialog.close()


def test_saved_file_content_matches_the_generated_preview_exactly(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()

    destination = tmp_path / "my_export.md"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(destination), ""))

    dialog._on_save_markdown_clicked()

    assert destination.read_text(encoding="utf-8") == dialog._markdown_text
    dialog.close()


def test_save_confirms_before_overwriting_an_existing_file(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()

    destination = tmp_path / "existing.md"
    destination.write_text("old content", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(destination), ""))

    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: (asked.append(True), QMessageBox.StandardButton.No)[1])

    dialog._on_save_markdown_clicked()

    assert asked
    assert destination.read_text(encoding="utf-8") == "old content"  # declined overwrite leaves it untouched
    dialog.close()


def test_no_evidence_state_shows_empty_materials_and_still_generates_a_preview(qapp, tmp_path):
    connection = open_connection(tmp_path / "empty.db")
    migrate(connection)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()

    assert dialog._bundle is not None
    assert dialog._bundle.materials == []
    assert "no materials matched" in dialog._markdown_text.lower()
    dialog.close()


# ---- stale-preview invalidation ----


def _assert_preview_is_stale(dialog):
    assert dialog._bundle is None
    assert dialog._markdown_text is None
    assert dialog._json_text is None
    assert dialog._evaluation_text is None
    for button in (
        dialog._save_markdown_button,
        dialog._save_json_button,
        dialog._save_template_button,
        dialog._copy_markdown_button,
        dialog._copy_json_button,
        dialog._copy_template_button,
    ):
        assert not button.isEnabled()


def test_changing_scope_invalidates_the_preview(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path, title="A")
    _make_material_with_cues(connection, tmp_path, title="B")

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()
    assert dialog._bundle is not None

    dialog._scope_combo.setCurrentIndex(1)  # One Material
    _assert_preview_is_stale(dialog)
    dialog.close()


def test_changing_selected_materials_invalidates_the_preview(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path, title="A")
    _make_material_with_cues(connection, tmp_path, title="B")

    dialog = ExportDialog(connection, None)
    dialog._scope_combo.setCurrentIndex(2)  # Selected Materials
    dialog._material_list.setCurrentRow(0)
    dialog._on_generate_preview_clicked()
    assert dialog._bundle is not None

    dialog._material_list.setCurrentRow(1)
    _assert_preview_is_stale(dialog)
    dialog.close()


def test_changing_date_preset_invalidates_the_preview(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()
    assert dialog._bundle is not None

    dialog._preset_combo.setCurrentIndex(1)
    _assert_preview_is_stale(dialog)
    dialog.close()


def test_changing_custom_dates_invalidates_the_preview(qapp, tmp_path):
    from PySide6.QtCore import QDate

    from listentrace.domain.services import date_range as date_range_rules
    from listentrace.ui.windows.export_dialog import _PRESET_LABELS

    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    custom_index = next(i for i, (_, preset) in enumerate(_PRESET_LABELS) if preset == date_range_rules.PRESET_CUSTOM)
    dialog._preset_combo.setCurrentIndex(custom_index)
    dialog._on_generate_preview_clicked()
    assert dialog._bundle is not None

    dialog._custom_start_edit.setDate(QDate.currentDate().addDays(-5))
    _assert_preview_is_stale(dialog)
    dialog.close()


def test_changing_evidence_categories_invalidates_the_preview(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()
    assert dialog._bundle is not None

    box = next(iter(dialog._category_checkboxes.values()))
    box.setChecked(not box.isChecked())
    _assert_preview_is_stale(dialog)
    dialog.close()


def test_changing_privacy_fields_invalidates_the_preview(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()
    assert dialog._bundle is not None

    box = next(iter(dialog._privacy_checkboxes.values()))
    box.setChecked(not box.isChecked())
    _assert_preview_is_stale(dialog)
    dialog.close()


def test_regenerating_after_invalidation_re_enables_save_and_copy(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()
    box = next(iter(dialog._category_checkboxes.values()))
    box.setChecked(not box.isChecked())
    assert not dialog._save_markdown_button.isEnabled()

    dialog._on_generate_preview_clicked()
    assert dialog._bundle is not None
    assert dialog._save_markdown_button.isEnabled()
    dialog.close()


def test_saved_output_always_corresponds_to_the_regenerated_selection(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)
    _make_material_with_cues(connection, tmp_path)

    dialog = ExportDialog(connection, None)
    dialog._on_generate_preview_clicked()
    original_categories = dialog._selected_categories()

    box = next(iter(dialog._category_checkboxes.values()))
    box.setChecked(not box.isChecked())
    assert dialog._selected_categories() != original_categories
    assert dialog._bundle is None  # stale, cannot be saved

    dialog._on_generate_preview_clicked()
    direct_bundle = export_service.build_export(
        connection,
        dialog._current_scope(),
        dialog._current_date_range(),
        dialog._selected_categories(),
        dialog._selected_privacy_fields(),
    )
    assert export_formatters.render_markdown(direct_bundle) == dialog._markdown_text
    dialog.close()


def test_learning_history_window_opens_export_dialog(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    opened = []
    monkeypatch.setattr(ExportDialog, "exec", lambda self: opened.append(True))

    window = LearningHistoryWindow(connection, tmp_path / "recordings")
    window._on_export_clicked()

    assert opened
    window.close()


def test_main_window_learning_history_leads_to_export_entry_point(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    opened = []
    monkeypatch.setattr(ExportDialog, "exec", lambda self: opened.append(True))

    window = MainWindow(connection, tmp_path / "smoke.db", tmp_path / "recordings")
    window._on_learning_history_clicked()
    window._learning_history_window._on_export_clicked()

    assert opened
    window._learning_history_window.close()
    window.close()
