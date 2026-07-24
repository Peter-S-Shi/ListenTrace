from __future__ import annotations

import struct
import wave

from listentrace.application.services import material_library_service as library
from listentrace.application.services.material_import_service import import_material
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.main_window import MainWindow


def _make_wav(path, seconds=1, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


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


def test_main_window_double_click_opens_player_for_active_material(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    import_material(connection, media, subtitle, "Lesson One")

    window = MainWindow(connection, tmp_path / "smoke.db")
    item = window._material_list.item(0)
    window._on_material_double_clicked(item)

    assert window._player_window is not None
    assert "Lesson One" in window._player_window.windowTitle()

    window._player_window.close()
    window.close()


def test_open_player_button_disabled_in_archived_view(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    library.archive_material(connection, result.material_id)

    window = MainWindow(connection, tmp_path / "smoke.db")
    window._on_toggle_archived()

    assert window._material_list.count() == 1
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._open_player_button.isEnabled() is False

    window.close()


def test_double_click_in_archived_view_does_not_open_player(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    library.archive_material(connection, result.material_id)

    window = MainWindow(connection, tmp_path / "smoke.db")
    window._on_toggle_archived()
    item = window._material_list.item(0)
    window._on_material_double_clicked(item)

    assert window._player_window is None

    window.close()
