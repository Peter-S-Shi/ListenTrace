from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from listentrace.application.services import quick_practice_service
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.learning_history_window import LearningHistoryWindow
from listentrace.ui.windows.main_window import MainWindow
from listentrace.ui.windows.player_window import PlayerWindow
from listentrace.ui.windows.quick_practice_start_dialog import QuickPracticeStartDialog
from listentrace.ui.windows.quick_practice_window import QuickPracticeWindow


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "entry_points.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _import_material(conn, tmp_path):
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nBonjour tout le monde\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nComment ca va\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nAu revoir\n",
        encoding="utf-8",
    )
    return import_material(conn, media_path, srt, "Entry Point Lesson")


def _fake_accepted_start_dialog(monkeypatch):
    """Bypasses the dialog's own UI to simulate an accepted Recommended
    Practice start — the dialog's own behavior is covered separately in
    test_quick_practice_start_dialog.py; these tests only verify each host
    window wires up to it and to QuickPracticeWindow correctly."""

    def fake_exec(self):
        session = quick_practice_service.start_recommended_session(self._connection, self._material_id, 5)
        self.started_session_id = session.id
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QuickPracticeStartDialog, "exec", fake_exec)


# ---- PlayerWindow ----


def test_player_window_quick_practice_this_cue_uses_the_editing_cue(qapp, conn, tmp_path):
    result = _import_material(conn, tmp_path)
    load_result = load_material_for_player(conn, result.material_id)
    window = PlayerWindow(load_result, conn)
    window._cue_list.setCurrentRow(1)

    window._on_quick_practice_this_cue_clicked()

    assert isinstance(window._quick_practice_window, QuickPracticeWindow)
    state = quick_practice_service.load_session_state(
        conn, window._quick_practice_window._session_id
    )
    assert [i.item.subtitle_cue_id for i in state.items] == [load_result.cues[1].id]
    window._quick_practice_window.close()
    window.close()


def test_player_window_quick_practice_selected_cues_preserves_range_order(qapp, conn, tmp_path):
    result = _import_material(conn, tmp_path)
    load_result = load_material_for_player(conn, result.material_id)
    window = PlayerWindow(load_result, conn)
    # Programmatically select the contiguous range rows 0-2 (interactive
    # Shift+click extension only applies to real mouse events, not
    # `setSelected` calls, so every row in the range is marked directly).
    window._cue_list.setCurrentRow(0)
    for row in range(3):
        window._cue_list.item(row).setSelected(True)

    window._on_quick_practice_selected_clicked()

    assert isinstance(window._quick_practice_window, QuickPracticeWindow)
    state = quick_practice_service.load_session_state(conn, window._quick_practice_window._session_id)
    assert [i.item.subtitle_cue_id for i in state.items] == [c.id for c in load_result.cues]
    window._quick_practice_window.close()
    window.close()


def test_player_window_quick_practice_selected_cues_falls_back_to_editing_cue(qapp, conn, tmp_path):
    result = _import_material(conn, tmp_path)
    load_result = load_material_for_player(conn, result.material_id)
    window = PlayerWindow(load_result, conn)
    window._cue_list.setCurrentRow(0)
    window._cue_list.clearSelection()

    window._on_quick_practice_selected_clicked()

    assert isinstance(window._quick_practice_window, QuickPracticeWindow)
    state = quick_practice_service.load_session_state(conn, window._quick_practice_window._session_id)
    assert [i.item.subtitle_cue_id for i in state.items] == [load_result.cues[0].id]
    window._quick_practice_window.close()
    window.close()


# ---- MainWindow ----


def test_main_window_quick_practice_opens_dialog_then_practice_window(qapp, conn, tmp_path, monkeypatch):
    result = _import_material(conn, tmp_path)
    _fake_accepted_start_dialog(monkeypatch)

    window = MainWindow(conn, tmp_path / "app.db", tmp_path / "recordings")

    # Select the imported material in the list.
    for i in range(window._material_list.count()):
        item = window._material_list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == result.material_id:
            window._material_list.setCurrentItem(item)
            break

    window._on_quick_practice_clicked()

    assert isinstance(window._quick_practice_window, QuickPracticeWindow)
    window._quick_practice_window.close()
    window.close()


# ---- LearningHistoryWindow ----


def test_learning_history_window_quick_practice_requires_a_selected_material(qapp, conn, tmp_path, monkeypatch):
    _import_material(conn, tmp_path)
    informed = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: informed.append(True)
    )
    window = LearningHistoryWindow(conn, tmp_path / "recordings")
    window._on_quick_practice_clicked()  # "All Materials" is selected by default
    assert informed
    window.close()


def test_learning_history_window_quick_practice_opens_practice_window(qapp, conn, tmp_path, monkeypatch):
    result = _import_material(conn, tmp_path)
    _fake_accepted_start_dialog(monkeypatch)

    window = LearningHistoryWindow(conn, tmp_path / "recordings", initial_material_id=result.material_id)
    window._on_quick_practice_clicked()

    assert isinstance(window._child_window, QuickPracticeWindow)
    window._child_window.close()
    window.close()
