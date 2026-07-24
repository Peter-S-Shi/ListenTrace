from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QLineEdit, QPushButton

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.player_state import LoopMode
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.ui.windows.player_window import PlayerWindow, _is_text_entry_widget


def _run_event_loop(app, timeout_ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _two_cue_result(media_path, media_kind="audio"):
    material = Material(id=1, title="Test Lesson", media_path=str(media_path), media_kind=media_kind)
    cues = [
        SubtitleCue(cue_index=1, start_ms=0, end_ms=500, text="hello"),
        SubtitleCue(cue_index=2, start_ms=500, end_ms=1000, text="world"),
    ]
    return PlayerLoadResult(material=material, cues=cues)


def test_is_text_entry_widget_helper(qapp):
    assert _is_text_entry_widget(QLineEdit()) is True
    assert _is_text_entry_widget(QPushButton()) is False
    assert _is_text_entry_widget(None) is False


def test_player_window_audio_mode_does_not_autoplay(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    _run_event_loop(qapp, 1500)

    assert window._audio_placeholder is not None
    assert window._video_widget is None
    assert window._playback.is_playing is False
    assert window._playback.position_ms == 0
    assert window._playback.duration_ms == pytest.approx(2000, abs=300)

    window.close()


def test_player_window_video_mode_creates_video_surface(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path, media_kind="video"))

    assert window._video_widget is not None
    assert window._audio_placeholder is None

    window.close()


def test_player_window_play_pause_toggle(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    window._on_play_pause_clicked()
    _run_event_loop(qapp, 500)
    assert window._playback.is_playing is True
    assert window._play_pause_button.text() == "Pause"

    window._on_play_pause_clicked()
    assert window._playback.is_playing is False
    assert window._play_pause_button.text() == "Play"

    window.close()


def test_player_window_invalid_media_produces_controlled_error(qapp, tmp_path):
    bad_path = tmp_path / "bad.mp3"
    bad_path.write_bytes(b"not a real mp3 file, just garbage bytes" * 20)

    window = PlayerWindow(_two_cue_result(bad_path))
    _run_event_loop(qapp, 2000)

    assert "Playback error" in window._status_label.text()
    assert window._play_pause_button.isEnabled() is False

    window.close()


def test_player_window_replay_cue_pauses_at_cue_end(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    window._cue_list.setCurrentRow(0)  # cue 0: 0-500ms
    window._on_replay_cue()

    _run_event_loop(qapp, 2000)

    assert window._playback.is_playing is False
    assert window._playback.position_ms == pytest.approx(500, abs=150)

    window.close()


def test_player_window_loop_cue_returns_to_start(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    window._cue_list.setCurrentRow(0)  # cue 0: 0-500ms
    window._on_loop_cue_clicked()

    assert window._session.loop_mode is LoopMode.CUE

    _run_event_loop(qapp, 1800)  # long enough to cross the 500ms boundary at least once

    assert window._playback.is_playing is True
    assert window._playback.position_ms < 500

    window.close()


def test_player_window_loop_range_returns_to_first_cue_start(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    window._cue_list.item(0).setSelected(True)
    window._cue_list.item(1).setSelected(True)
    window._on_loop_range_clicked()

    assert window._session.loop_mode is LoopMode.RANGE
    assert window._session.selected_range == (0, 1)

    _run_event_loop(qapp, 2200)  # long enough to cross the 1000ms range end at least once

    assert window._playback.is_playing is True
    assert window._playback.position_ms < 1000

    window.close()


def test_player_window_cancel_loop_stops_boundary_seeks(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    window._cue_list.setCurrentRow(0)
    window._on_loop_cue_clicked()
    window._session.cancel_loop()

    assert window._session.loop_mode is LoopMode.NONE

    window.close()


def test_player_window_toggle_transcript_keeps_active_cue_tracking(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    window._on_toggle_transcript()

    assert window._session.transcript_visible is False
    assert window._cue_list.isVisible() is False

    window._on_position_changed(600)
    assert window._session.active_cue_index == 1

    window.close()


def test_player_window_mute_toggle(qapp, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path))
    assert window._playback.is_muted is False

    window._on_toggle_mute()
    assert window._playback.is_muted is True
    assert window._mute_button.text() == "Unmute"

    window._on_toggle_mute()
    assert window._playback.is_muted is False

    window.close()
