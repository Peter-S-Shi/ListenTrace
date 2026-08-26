from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

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

    # Check primary role
    assert window._open_player_button.property("role") == "primary"
    assert window._remove_button.property("role") == "danger"

    window.close()
