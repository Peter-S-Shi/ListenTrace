from __future__ import annotations

from listentrace.application.services.material_import_service import import_material
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.main_window import MainWindow


def test_main_window_starts_with_initialized_database(qapp, tmp_path):
    db_path = tmp_path / "smoke.db"
    connection = open_connection(db_path)
    migrate(connection)

    window = MainWindow(connection, db_path)

    assert window.windowTitle() == "ListenTrace"
    assert "Schema version: 2" in window._status_label.text()

    window.close()


def test_main_window_shows_empty_library_state(qapp, tmp_path):
    connection = open_connection(tmp_path / "empty.db")
    migrate(connection)

    window = MainWindow(connection, tmp_path / "empty.db")

    assert window._material_list.count() == 1
    assert "empty" in window._material_list.item(0).text().lower()

    window.close()


def test_main_window_lists_imported_material_and_shows_detail(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.mp3"
    media.write_bytes(b"fake audio bytes" * 50)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    import_material(connection, media, subtitle, "Lesson One")

    window = MainWindow(connection, tmp_path / "smoke.db")

    assert window._material_list.count() == 1
    item = window._material_list.item(0)
    assert item.text() == "Lesson One"

    window._material_list.setCurrentItem(item)
    assert "Lesson One" in window._detail_label.text()
    assert "Cue count: 1" in window._detail_label.text()
    assert window._rename_button.isEnabled()

    window.close()
