from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from listentrace.application.services import loop_grace_service
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog
from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "shadowing.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=4, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _pump(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_play_button_is_cue_scoped_not_whole_media(qapp, conn, tmp_path):
    """M12 Round 1 Playback Contract (P1): Play must stop at the current
    cue's end, not drift into the next cue's audio -- confirmed during Phase 0
    that Shadowing shares the exact same whole-media Play defect as Quiz and
    Quick Practice, even though its cue navigation itself was already correct."""
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nBonjour\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nComment ca va\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nAu revoir\n",
        encoding="utf-8",
    )
    result = import_material(conn, media_path, srt, "Shadowing Lesson")
    load_result = load_material_for_player(conn, result.material_id)
    cue = load_result.cues[1]  # 1000-2000ms
    window = ShadowingPracticeWindow(conn, load_result, tmp_path / "recordings", initial_cue_id=cue.id)
    _pump(500)  # let the async media load finish before seeking away from position 0

    window._on_play_clicked()
    _pump((cue.end_ms - cue.start_ms) + 500)

    assert window._playback.is_playing is False, (
        "Play must stop at this cue's end, not continue playing into the next cue"
    )
    assert window._playback.position_ms < cue.end_ms + 200
    window.close()


def test_loop_settings_button_opens_a_material_loop_settings_dialog(qapp, conn, tmp_path):
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")
    result = import_material(conn, media_path, srt, "Shadowing Lesson 2")
    load_result = load_material_for_player(conn, result.material_id)
    window = ShadowingPracticeWindow(conn, load_result, tmp_path / "recordings")

    window._on_open_loop_settings()

    assert isinstance(window._loop_settings_dialog, MaterialLoopSettingsDialog)
    window.close()


def test_material_override_changed_updates_this_windows_live_session_grace(qapp, conn, tmp_path):
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")
    result = import_material(conn, media_path, srt, "Shadowing Lesson 3")
    load_result = load_material_for_player(conn, result.material_id)
    window = ShadowingPracticeWindow(conn, load_result, tmp_path / "recordings")

    loop_grace_service.set_material_loop_end_grace_override_ms(conn, result.material_id, 90)
    loop_grace_change_bus.material_override_changed.emit(result.material_id)

    assert window._player_session._loop_end_grace_ms == 90
    window.close()
