from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog

from listentrace.application.services.material_import_service import import_material
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.main_window import MainWindow


from PySide6.QtCore import QSettings
from listentrace.ui.windows.main_window import _SETTINGS_ORG, _SETTINGS_APP


@pytest.fixture()
def db_conn(tmp_path):
    _settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    _settings.clear()
    db_file = tmp_path / "test_main.db"
    conn = open_connection(db_file)
    migrate(conn)
    yield conn, db_file
    conn.close()
    _settings.clear()


def test_main_window_sidebar_collapse_and_restore(qapp, db_conn, tmp_path):
    conn, db_file = db_conn
    window = MainWindow(conn, db_file, tmp_path / "recordings")
    window.show()

    assert window._sidebar_collapsed is False
    assert window._sidebar_widget.isVisible() is True
    assert window._nav_library_button.property("role") == "nav_item"

    # Toggle to collapse
    window._on_toggle_sidebar()
    assert window._sidebar_collapsed is True
    assert window._sidebar_widget.isVisible() is False

    # Toggle to restore
    window._on_toggle_sidebar()
    assert window._sidebar_collapsed is False
    assert window._sidebar_widget.isVisible() is True

    window.close()


def test_main_window_material_selection_and_action_hierarchy(qapp, db_conn, tmp_path):
    conn, db_file = db_conn
    media_file = tmp_path / "sample.mp3"
    media_file.write_bytes(b"dummy audio content" * 20)
    srt_file = tmp_path / "sample.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    import_material(conn, media_file, srt_file, "Test Lesson M13")

    window = MainWindow(conn, db_file, tmp_path / "recordings")

    # Initial state: 1 item, not selected yet
    assert window._material_list.count() == 1
    assert window._material_list.property("role") == "ruled_list"
    assert window._open_player_button.isEnabled() is False

    # Select material item
    item = window._material_list.item(0)
    window._material_list.setCurrentItem(item)

    # Context Inspector should update
    assert window._open_player_button.isEnabled() is True
    assert window._start_intensive_button.isEnabled() is True
    assert window._remove_button.isEnabled() is True
    assert "Test Lesson M13" in window._detail_label.text()
    assert "Cue count: 1" in window._detail_label.text()

    # Verify structured 7-row ruled dossier metadata values
    assert window._row_title._value.text() == "Test Lesson M13"
    assert window._row_status._value.text() == "active"
    assert window._row_media._value.text() == "sample.mp3"
    assert window._row_sub_format._value.text() == "srt"
    assert window._row_subtitle._value.text() == "sample.srt"
    assert window._row_cue_count._value.text() == "1"

    # Check primary role
    assert window._open_player_button.property("role") == "primary"
    assert window._remove_button.property("role") == "danger"

    window.close()


def test_rename_preserves_library_selection_by_material_id(qapp, db_conn, tmp_path, monkeypatch):
    """M14 Corrective Batch A (A1): the renamed material must stay selected
    even though its alphabetical row position moves and the list is fully
    rebuilt -- selection must be tracked by material_id, not row index."""
    conn, db_file = db_conn
    media_a = tmp_path / "a.mp3"
    media_a.write_bytes(b"dummy audio content" * 20)
    srt_a = tmp_path / "a.srt"
    srt_a.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    result_a = import_material(conn, media_a, srt_a, "Alpha Lesson")

    media_b = tmp_path / "b.mp3"
    media_b.write_bytes(b"dummy audio content" * 20)
    srt_b = tmp_path / "b.srt"
    srt_b.write_text("1\n00:00:00,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
    import_material(conn, media_b, srt_b, "Beta Lesson")

    window = MainWindow(conn, db_file, tmp_path / "recordings")

    for i in range(window._material_list.count()):
        item = window._material_list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == result_a.material_id:
            window._material_list.setCurrentItem(item)
            break
    assert window._selected_material_id() == result_a.material_id

    # Rename to a title that sorts after "Beta Lesson" -- forces the renamed
    # item into a new row position once the list is rebuilt.
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Zulu Lesson", True))
    window._on_rename_clicked()

    assert window._selected_material_id() == result_a.material_id
    assert window._open_player_button.isEnabled() is True
    assert "Zulu Lesson" in window._detail_label.text()
    assert window._row_title._value.text() == "Zulu Lesson"
    window.close()


def test_archiving_correctly_leaves_selection_empty_not_a_regression(qapp, db_conn, tmp_path):
    """Companion to A1: archiving/restoring/removing a material correctly
    makes it leave the currently-displayed list -- this must NOT be
    "fixed" into staying selected, since that would misrepresent a material
    that is no longer in the active view."""
    conn, db_file = db_conn
    media = tmp_path / "a.mp3"
    media.write_bytes(b"dummy audio content" * 20)
    srt = tmp_path / "a.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    import_material(conn, media, srt, "Alpha Lesson")

    window = MainWindow(conn, db_file, tmp_path / "recordings")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._selected_material_id() is not None

    window._on_archive_restore_clicked()

    assert window._selected_material_id() is None
    assert window._open_player_button.isEnabled() is False
    window.close()


def test_rename_propagates_to_open_player_window_title_and_header(qapp, db_conn, tmp_path, monkeypatch):
    """M14 Corrective Batch A (A2): an already-open PlayerWindow's title bar
    and in-body header must refresh from a Library rename without being
    closed and reopened."""
    conn, db_file = db_conn
    media = tmp_path / "a.mp3"
    media.write_bytes(b"dummy audio content" * 20)
    srt = tmp_path / "a.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    result = import_material(conn, media, srt, "Original Title")

    window = MainWindow(conn, db_file, tmp_path / "recordings")
    window._open_player(result.material_id)
    player = window._player_window
    assert "Original Title" in player.windowTitle()
    assert player._header_title_label.text() == "Original Title"

    window._material_list.setCurrentItem(window._material_list.item(0))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Renamed Title", True))
    window._on_rename_clicked()

    assert "Renamed Title" in player.windowTitle()
    assert "Original Title" not in player.windowTitle()
    assert player._header_title_label.text() == "Renamed Title"
    assert player._material.title == "Renamed Title"

    player.close()
    window.close()


def test_main_window_settings_button_opens_settings_dialog(qapp, db_conn, tmp_path):
    conn, db_file = db_conn
    window = MainWindow(conn, db_file, tmp_path / "recordings")
    window.show()

    assert window._settings_button.text() == "Settings..."
    assert window._settings_button.property("role") == "nav_item"

    # Click settings button to open SettingsDialog
    window._settings_button.click()
    assert window._settings_dialog is not None
    assert window._settings_dialog.isVisible() is True
    assert window._settings_dialog.windowTitle() == "Settings"

    window._settings_dialog.close()
    window.close()
