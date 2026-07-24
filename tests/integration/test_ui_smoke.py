from __future__ import annotations

import struct
import wave

from PySide6.QtWidgets import QMessageBox

from listentrace.application.services import material_library_service as library
from listentrace.application.services import practice_session_service as session_service
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
    assert "Schema version: 4" in window._status_label.text()

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


def test_start_intensive_practice_opens_guided_window_and_enables_resume(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")

    window = MainWindow(connection, tmp_path / "smoke.db")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._resume_intensive_button.isEnabled() is False

    window._on_start_intensive_clicked()

    assert window._guided_session_window is not None
    assert session_service.find_active_session(connection, result.material_id) is not None
    assert window._resume_intensive_button.isEnabled() is True

    window._guided_session_window.close()
    window.close()


def test_start_intensive_practice_with_active_session_offers_resume_choice(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    existing = session_service.start_session(connection, result.material_id)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    window = MainWindow(connection, tmp_path / "smoke.db")
    window._material_list.setCurrentItem(window._material_list.item(0))
    window._on_start_intensive_clicked()

    # "Yes" maps to Resume: no second session should be created.
    sessions = session_service.list_sessions_for_material(connection, result.material_id)
    assert len(sessions) == 1
    assert sessions[0].id == existing.id

    window._guided_session_window.close()
    window.close()


def test_start_intensive_practice_abandon_and_start_new(qapp, tmp_path, monkeypatch):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    existing = session_service.start_session(connection, result.material_id)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    window = MainWindow(connection, tmp_path / "smoke.db")
    window._material_list.setCurrentItem(window._material_list.item(0))
    window._on_start_intensive_clicked()

    sessions = session_service.list_sessions_for_material(connection, result.material_id)
    assert len(sessions) == 2
    old_session = next(s for s in sessions if s.id == existing.id)
    assert old_session.status == "abandoned"
    new_session = next(s for s in sessions if s.id != existing.id)
    assert new_session.status == "active"

    window._guided_session_window.close()
    window.close()


def test_resume_intensive_practice_button_opens_active_session(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    session_service.start_session(connection, result.material_id)

    window = MainWindow(connection, tmp_path / "smoke.db")
    window._material_list.setCurrentItem(window._material_list.item(0))
    assert window._resume_intensive_button.isEnabled() is True

    window._on_resume_intensive_clicked()
    assert window._guided_session_window is not None

    window._guided_session_window.close()
    window.close()


def test_session_history_dialog_opens_selected_session(qapp, tmp_path):
    connection = open_connection(tmp_path / "smoke.db")
    migrate(connection)

    media = tmp_path / "lesson.wav"
    _make_wav(media)
    subtitle = tmp_path / "lesson.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(connection, media, subtitle, "Lesson One")
    first = session_service.start_session(connection, result.material_id)
    session_service.abandon_session(connection, first.id)
    second = session_service.start_session(connection, result.material_id)
    session_service.abandon_session(connection, second.id)

    window = MainWindow(connection, tmp_path / "smoke.db")
    window._material_list.setCurrentItem(window._material_list.item(0))

    from listentrace.ui.windows.session_history_dialog import SessionHistoryDialog

    dialog = SessionHistoryDialog(connection, result.material_id, "Lesson One", window)
    assert dialog._list.count() == 2
    dialog._list.setCurrentRow(0)
    dialog._on_open_clicked()
    assert dialog.selected_session_id in (first.id, second.id)

    window._open_guided_session(result.material_id, dialog.selected_session_id)
    assert window._guided_session_window is not None
    # A closed (abandoned) session opens read-only.
    assert window._guided_session_window._continue_button.isEnabled() is False

    window._guided_session_window.close()
    window.close()
